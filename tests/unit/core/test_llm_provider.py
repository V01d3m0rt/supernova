from unittest.mock import patch, MagicMock, AsyncMock
from functools import partial
import asyncio

import pytest

from supernova.core.llm_provider import LLMProvider
from supernova.config.schema import SuperNovaConfig, LLMProviderConfig
import litellm


@pytest.fixture
def mock_loop():
    """Create a mock for the asyncio event loop."""
    loop = AsyncMock()
    loop.run_in_executor.return_value = MagicMock()
    return loop


@pytest.fixture
def mock_response():
    """Create a mock response that mimics the structure expected in LLMProvider."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message = MagicMock()
    response.choices[0].message.content = "Test response"
    response.choices[0].message.tool_calls = []
    return response


@pytest.fixture
def provider_config():
    """Create a test provider configuration."""
    return LLMProviderConfig(
        provider="openai",
        base_url="https://api.test.com",
        api_key="test_key",
        model="test-model",
        is_default=True,
        temperature=0.7,
        max_tokens=1000
    )


@pytest.fixture
def test_config(provider_config):
    """Create a test configuration with the provider config."""
    return SuperNovaConfig(
        llm_providers={"test_provider": provider_config},
        project_context={"key_files": ["README.md"]},
        chat={"history_limit": 10},
        command_execution={"require_confirmation": True},
        extensions={"enabled": True},
        persistence={"enabled": True},
        debugging={"show_traceback": False}
    )


@pytest.mark.asyncio
async def test_llm_provider_init_default_provider(test_config):
    """Test LLMProvider initialization with default provider."""
    with patch("supernova.core.llm_provider.loader.load_config", return_value=test_config):
        provider = LLMProvider()
        assert provider.provider_config.provider == "openai"
        assert provider.provider_config.api_key == "test_key"
        assert provider.provider_config.model == "test-model"


@pytest.mark.asyncio
async def test_llm_provider_init_specific_provider(test_config):
    """Test LLMProvider initialization with a specific provider."""
    # Add another provider to config
    second_provider = LLMProviderConfig(
        provider="anthropic",
        base_url="https://api.second.com",
        api_key="second_key",
        model="second-model",
        is_default=False
    )
    test_config.llm_providers["second_provider"] = second_provider
    
    with patch("supernova.core.llm_provider.loader.load_config", return_value=test_config):
        provider = LLMProvider("second_provider")
        assert provider.provider_config.provider == "anthropic"
        assert provider.provider_config.api_key == "second_key"
        assert provider.provider_config.model == "second-model"


@pytest.mark.asyncio
async def test_llm_provider_init_invalid_provider(test_config):
    """Test LLMProvider initialization with an invalid provider."""
    with patch("supernova.core.llm_provider.loader.load_config", return_value=test_config):
        with pytest.raises(ValueError):
            LLMProvider("nonexistent_provider")


@pytest.mark.asyncio
async def test_get_completion_non_streaming(test_config, mock_response, mock_loop):
    """Test getting a completion from the LLM without streaming."""
    with patch("supernova.core.llm_provider.loader.load_config", return_value=test_config):
        with patch("asyncio.get_event_loop", return_value=mock_loop):
            # Set up the mock loop to return our mock response
            mock_loop.run_in_executor.return_value = mock_response
            
            provider = LLMProvider()
            
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello"}
            ]
            
            response = await provider.get_completion(messages=messages, stream=False)
            
            # Verify run_in_executor was called 
            mock_loop.run_in_executor.assert_called_once()
            
            # Get the args passed to run_in_executor
            call_args = mock_loop.run_in_executor.call_args[0]
            
            # The first arg is None (the executor)
            assert call_args[0] is None
            
            # The second arg is a partial function
            assert isinstance(call_args[1], partial)
            
            # Verify response content is correctly extracted
            assert "content" in response
            assert response["content"] == "Test response"


@pytest.mark.asyncio
async def test_get_completion_with_tools(test_config, mock_loop):
    """Test getting a completion with tools configuration."""
    # Create mock response with tool calls
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message = MagicMock()
    mock_response.choices[0].message.content = "Test response"
    
    tool_call = MagicMock()
    tool_call.id = "call_1"
    tool_call.type = "function"
    tool_call.function = MagicMock()
    tool_call.function.name = "test_tool"
    tool_call.function.arguments = '{"arg1":"value1"}'
    
    mock_response.choices[0].message.tool_calls = [tool_call]
    
    with patch("supernova.core.llm_provider.loader.load_config", return_value=test_config):
        with patch("asyncio.get_event_loop", return_value=mock_loop):
            # Set up the mock loop to return our mock response
            mock_loop.run_in_executor.return_value = mock_response
            
            # Also patch supports_tool_calling to return True
            with patch.object(LLMProvider, 'supports_tool_calling', return_value=True):
                provider = LLMProvider()
                
                tools = [
                    {
                        "type": "function",
                        "function": {
                            "name": "test_tool",
                            "description": "A test tool",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "arg1": {"type": "string"}
                                },
                                "required": ["arg1"]
                            }
                        }
                    }
                ]
                
                messages = [{"role": "user", "content": "Use a tool"}]
                response = await provider.get_completion(messages=messages, tools=tools)
                
                # Verify run_in_executor was called
                mock_loop.run_in_executor.assert_called_once()
                
                # Get the partial function passed to run_in_executor
                partial_fn = mock_loop.run_in_executor.call_args[0][1]
                
                # Verify tools were included in the call
                kwargs = partial_fn.keywords
                assert "tools" in kwargs
                assert kwargs["tools"] == tools
                
                # Verify response tool calls were extracted
                assert "tool_calls" in response
                assert len(response["tool_calls"]) > 0
                assert response["tool_calls"][0].function.name == "test_tool"


@pytest.mark.asyncio
async def test_handle_api_error(test_config, mock_loop):
    """Test handling of API errors."""
    with patch("supernova.core.llm_provider.loader.load_config", return_value=test_config):
        with patch("asyncio.get_event_loop", return_value=mock_loop):
            # Make run_in_executor raise an exception
            mock_loop.run_in_executor.side_effect = Exception("API Error")
            
            provider = LLMProvider()
            
            messages = [{"role": "user", "content": "Hello"}]
            
            # Should return error message instead of raising exception
            response = await provider.get_completion(messages=messages)
            
            # Check that the response contains the error message
            assert "content" in response
            assert "Error" in response["content"]
            assert "API Error" in response["content"]


@pytest.mark.asyncio
async def test_supports_tool_calling(test_config):
    """Test detection of tool calling capability."""
    with patch("supernova.core.llm_provider.loader.load_config", return_value=test_config):
        provider = LLMProvider()
        
        # Test with a model known to support tool calling
        with patch.object(LLMProvider, 'known_tool_capable_models', ["test"]):
            provider.provider_config.model = "test-model"
            assert provider.supports_tool_calling() is True
        
        # Test with a model that might not support tool calling
        with patch('litellm.supports_function_calling', return_value=False):
            provider.provider_config.model = "unknown-model"
            assert provider.supports_tool_calling() is False


@pytest.mark.asyncio
async def test_sanitize_response_content(test_config):
    """Test sanitizing content from LLM responses."""
    with patch("supernova.core.llm_provider.loader.load_config", return_value=test_config):
        provider = LLMProvider()
        
        # Test with normal content
        content = "This is a normal response."
        assert provider._sanitize_response_content(content) == content
        
        # Test with JSON content containing a content field
        json_content = '{"content": "Extracted content", "other_field": "value"}'
        assert provider._sanitize_response_content(json_content) == "Extracted content"
        
        # Test with terminal command pattern
        cmd_content = 'Here\'s a command: terminal_command {"command": "ls -la", "explanation": "List files"}'
        sanitized = provider._sanitize_response_content(cmd_content)
        assert "terminal_command" not in sanitized
        assert "[I would execute: `ls -la`]" in sanitized 


@pytest.mark.asyncio
async def test_extract_tool_calls_from_text(test_config):
    """Test extraction of tool calls from text."""
    with patch("supernova.core.llm_provider.loader.load_config", return_value=test_config):
        provider = LLMProvider()
        
        # Test with terminal command
        content = 'Let me help you with that. terminal_command {"command": "ls -la", "explanation": "List files"}'
        result = provider._extract_tool_calls_from_text(content)
        assert "terminal_command" not in result
        assert "[I would execute: `ls -la`]" in result
        
        # Test with Maven command
        maven_content = 'You should execute Maven command "mvn clean install"'
        result = provider._extract_tool_calls_from_text(maven_content)
        assert "mvn clean install" in result
        assert "[I would run Maven:" in result
        
        # Test with normal content
        normal_content = "This is normal text with no commands."
        result = provider._extract_tool_calls_from_text(normal_content)
        assert result == normal_content


@pytest.mark.asyncio
async def test_get_token_count(test_config, mock_loop):
    """Test token counting functionality."""
    with patch("supernova.core.llm_provider.loader.load_config", return_value=test_config):
        with patch("asyncio.get_event_loop", return_value=mock_loop):
            provider = LLMProvider()
            
            # Test with litellm.token_counter available
            with patch.object(litellm, "token_counter", return_value=10):
                # Set the return value for run_in_executor
                mock_loop.run_in_executor.return_value = 10
                token_count = await provider.get_token_count("Test text")
                assert token_count == 10
                
            # Test fallback when token_counter raises exception
            with patch.object(litellm, "token_counter", side_effect=Exception("Token counter error")):
                # Make run_in_executor raise an exception to trigger the fallback
                mock_loop.run_in_executor.side_effect = Exception("Token counter error")
                token_count = await provider.get_token_count("Test text")
                # Should use the fallback (length // 4)
                assert token_count == len("Test text") // 4
                
            # Test when token_counter is not available
            original_has_attr = hasattr
            
            def mock_hasattr(obj, name):
                if obj == litellm and name == "token_counter":
                    return False
                return original_has_attr(obj, name)
            
            with patch("builtins.hasattr", mock_hasattr):
                # Reset the side_effect
                mock_loop.run_in_executor.side_effect = None
                token_count = await provider.get_token_count("Test text longer than four chars")
                # Should use the fallback (length // 4)
                assert token_count == len("Test text longer than four chars") // 4 


@pytest.mark.asyncio
async def test_is_repeating_failed_command(test_config):
    """Test detection of repeating failed commands."""
    with patch("supernova.core.llm_provider.loader.load_config", return_value=test_config):
        provider = LLMProvider()
        
        # Empty failed commands list
        assert not provider.is_repeating_failed_command(
            "terminal_command", 
            {"command": "ls -la"}, 
            []
        )
        
        # Non-terminal command tool
        assert not provider.is_repeating_failed_command(
            "other_tool", 
            {"arg": "value"}, 
            [{"tool": "terminal_command", "args": {"command": "ls -la"}}]
        )
        
        # Different terminal command
        assert not provider.is_repeating_failed_command(
            "terminal_command", 
            {"command": "echo hello"}, 
            [{"tool": "terminal_command", "args": {"command": "ls -la"}}]
        )
        
        # Repeating terminal command
        assert provider.is_repeating_failed_command(
            "terminal_command", 
            {"command": "ls -la"}, 
            [{"tool": "terminal_command", "args": {"command": "ls -la"}}]
        )
        
        # Repeating with whitespace differences
        assert provider.is_repeating_failed_command(
            "terminal_command", 
            {"command": "ls -la  "}, 
            [{"tool": "terminal_command", "args": {"command": "ls -la"}}]
        )


@pytest.mark.asyncio
async def test_add_tool_capable_model():
    """Test adding tool capable models to the known list."""
    # Save original list of models
    original_models = LLMProvider.known_tool_capable_models.copy()
    
    try:
        # Test adding a new model
        LLMProvider.add_tool_capable_model("test-model")
        assert "test-model" in LLMProvider.known_tool_capable_models
        
        # Test adding a model with whitespace
        LLMProvider.add_tool_capable_model("  another-model  ")
        assert "another-model" in LLMProvider.known_tool_capable_models
        
        # Test adding a duplicate model (should not create duplicates)
        original_length = len(LLMProvider.known_tool_capable_models)
        LLMProvider.add_tool_capable_model("test-model")
        assert len(LLMProvider.known_tool_capable_models) == original_length
        
        # Test adding an empty string (should be ignored)
        original_length = len(LLMProvider.known_tool_capable_models)
        LLMProvider.add_tool_capable_model("")
        assert len(LLMProvider.known_tool_capable_models) == original_length
        
    finally:
        # Restore original list
        LLMProvider.known_tool_capable_models = original_models 


@pytest.mark.asyncio
async def test_get_completion_streaming(test_config, mock_loop):
    """Test getting a streaming completion from the LLM."""
    with patch("supernova.core.llm_provider.loader.load_config", return_value=test_config):
        with patch("asyncio.get_event_loop", return_value=mock_loop):
            provider = LLMProvider()
            
            # Create a callback for streaming
            callback_results = []
            def stream_callback(data):
                callback_results.append(data)
            
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello"}
            ]
            
            # Mock the run_in_executor response
            mock_loop.run_in_executor.return_value = {"content": "", "tool_calls": []}
            
            # Test streaming response
            response = await provider.get_completion(messages=messages, stream=True, stream_callback=stream_callback)
            
            # Verify that run_in_executor was called
            mock_loop.run_in_executor.assert_called_once()
            
            # Verify that the partial function passed to run_in_executor has correct parameters
            partial_fn = mock_loop.run_in_executor.call_args[0][1]
            kwargs = partial_fn.keywords
            
            # Check the parameters
            assert kwargs["stream"] is True
            assert "stream_options" in kwargs
            assert "callback" in kwargs
            
            # Check the empty response
            assert response["content"] == ""
            assert response["tool_calls"] == []


@pytest.mark.asyncio
async def test_process_streaming_response(test_config):
    """Test processing of streaming response chunks."""
    with patch("supernova.core.llm_provider.loader.load_config", return_value=test_config):
        provider = LLMProvider()
        
        # Create a mock chunk with content
        content_chunk = MagicMock()
        content_chunk.choices = [MagicMock()]
        content_chunk.choices[0].delta = MagicMock()
        content_chunk.choices[0].delta.content = "Hello world"
        content_chunk.choices[0].delta.tool_calls = None
        
        # Process the content chunk
        result = provider.process_streaming_response(content_chunk)
        
        # Verify content was extracted
        assert result["content"] == "Hello world"
        assert result["tool_calls"] == []
        
        # Create a mock chunk with tool calls
        tool_call_chunk = MagicMock()
        tool_call_chunk.choices = [MagicMock()]
        tool_call_chunk.choices[0].delta = MagicMock()
        tool_call_chunk.choices[0].delta.content = None
        
        # Create a tool_calls list that will be returned by getattr
        tool_calls_list = ["mock_tool_call"]
        setattr(tool_call_chunk.choices[0].delta, 'tool_calls', tool_calls_list)
        
        # Process the tool call chunk
        result = provider.process_streaming_response(tool_call_chunk)
        
        # Verify tool call was extracted
        assert result["content"] == ""
        assert result["tool_calls"] == tool_calls_list
        
        # Test with accumulated content
        result = provider.process_streaming_response(
            content_chunk, 
            accumulated_content="Previous ",
            accumulated_tool_calls=["previous_call"]
        )
        
        # Verify content and tool calls were accumulated
        assert result["content"] == "Hello world"
        assert result["tool_calls"] == [] 