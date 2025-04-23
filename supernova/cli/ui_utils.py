"""
SuperNova - AI-powered development assistant within the terminal.

UI utilities and animations for the CLI interface.
"""

import time
import threading
import itertools
import sys
from typing import Callable, List, Optional, Any, Dict, Union
from contextlib import contextmanager

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.live import Live
from rich.layout import Layout
from rich.text import Text
from rich.style import Style
from rich.box import Box, ROUNDED

console = Console()

# Custom spinner patterns
SPINNERS = {
    "dots": ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
    "line": ["-", "\\", "|", "/"],
    "pulse": ["█", "▓", "▒", "░", "▒", "▓"],
    "stars": ["✶", "✸", "✹", "✺", "✹", "✷"],
    "moon": ["🌑", "🌒", "🌓", "🌔", "🌕", "🌖", "🌗", "🌘"],
    "braille": ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"],
    "supernova": ["✨", "💫", "🌟", "⭐", "✨", "💫", "🌟", "⭐"]
}

# Color themes
THEMES = {
    "default": {
        "primary": "cyan",
        "secondary": "blue",
        "success": "green",
        "warning": "yellow",
        "error": "red",
        "info": "white",
        "highlight": "magenta"
    },
    "dark": {
        "primary": "bright_cyan",
        "secondary": "bright_blue",
        "success": "bright_green",
        "warning": "bright_yellow",
        "error": "bright_red",
        "info": "bright_white",
        "highlight": "bright_magenta"
    }
}

# Current theme
current_theme = "default"

def set_theme(theme_name: str) -> None:
    """
    Set the current color theme.
    
    Args:
        theme_name: Name of the theme to use
    """
    global current_theme
    if theme_name in THEMES:
        current_theme = theme_name
    else:
        console.print(f"[yellow]Warning:[/yellow] Theme '{theme_name}' not found. Using default.")
        current_theme = "default"

def theme_color(color_name: str) -> str:
    """
    Get a color from the current theme.
    
    Args:
        color_name: Name of the color to get
        
    Returns:
        Color string for Rich formatting
    """
    theme = THEMES.get(current_theme, THEMES["default"])
    return theme.get(color_name, "white")

@contextmanager
def loading_animation(message: str, spinner: str = "supernova"):
    """
    Context manager for displaying a loading animation.
    
    Args:
        message: Message to display alongside the spinner
        spinner: Name of the spinner pattern to use
    """
    spinner_pattern = SPINNERS.get(spinner, SPINNERS["dots"])
    stop_event = threading.Event()
    
    def spin():
        spinner_cycle = itertools.cycle(spinner_pattern)
        while not stop_event.is_set():
            sys.stdout.write(f"\r{next(spinner_cycle)} {message}")
            sys.stdout.flush()
            time.sleep(0.1)
        # Clear the line when done
        sys.stdout.write("\r" + " " * (len(message) + 2) + "\r")
        sys.stdout.flush()
    
    # Start spinner in a separate thread
    spinner_thread = threading.Thread(target=spin)
    spinner_thread.daemon = True
    spinner_thread.start()
    
    try:
        yield
    finally:
        stop_event.set()
        spinner_thread.join()

def animated_print(text: str, delay: float = 0.01, end: str = "\n") -> None:
    """
    Print text with a typing animation effect.
    
    Args:
        text: Text to print
        delay: Delay between characters in seconds
        end: String to append at the end
    """
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write(end)
    sys.stdout.flush()

def display_welcome_banner() -> None:
    """Display an animated welcome banner for SuperNova with flying elements."""
    try:
        # Clear the screen
        console.clear()
        
        # Animation frames for flying elements
        rocket_frames = [
            "    🚀       ✨         💻         🔍    ",
            "  🚀         ✨       💻           🔍  ",
            "🚀           ✨     💻             🔍",
            "  🚀         ✨       💻           🔍  ",
            "    🚀       ✨         💻         🔍    ",
            "      🚀     ✨           💻       🔍      ",
            "        🚀   ✨             💻     🔍        ",
            "          🚀 ✨               💻   🔍          ",
            "            🚀✨                 💻 🔍            ",
            "          🚀 ✨               💻   🔍          ",
            "        🚀   ✨             💻     🔍        ",
            "      🚀     ✨           💻       🔍      "
        ]
        
        # Code snippets flying by
        code_snippets = [
            "def hello_world():",
            "import supernova",
            "class SuperNova:",
            "async def run():",
            "from supernova import AI",
            "# AI-powered coding",
            "git commit -m 'Fix'",
            "npm install supernova",
            "pip install supernova"
        ]
        
        # SuperNova ASCII art
        supernova_art = """
        ███████╗██╗   ██╗██████╗ ███████╗██████╗ ███╗   ██╗ ██████╗ ██╗   ██╗ █████╗ 
        ██╔════╝██║   ██║██╔══██╗██╔════╝██╔══██╗████╗  ██║██╔═══██╗██║   ██║██╔══██╗
        ███████╗██║   ██║██████╔╝█████╗  ██████╔╝██╔██╗ ██║██║   ██║██║   ██║███████║
        ╚════██║██║   ██║██╔═══╝ ██╔══╝  ██╔══██╗██║╚██╗██║██║   ██║╚██╗ ██╔╝██╔══██║
        ███████║╚██████╔╝██║     ███████╗██║  ██║██║ ╚████║╚██████╔╝ ╚████╔╝ ██║  ██║
        ╚══════╝ ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝ ╚═════╝   ╚═══╝  ╚═╝  ╚═╝
        """
        
        # Animate flying elements before showing the main banner
        for i in range(10):  # Show 10 frames of animation
            # Select a random code snippet
            import random
            snippet_idx = random.randint(0, len(code_snippets) - 1)
            snippet = code_snippets[snippet_idx]
            
            # Create a frame with flying elements
            frame = rocket_frames[i % len(rocket_frames)]
            
            # Print the frame
            sys.stdout.write("\r" + " " * 80 + "\r")  # Clear line
            sys.stdout.write(f"\r{frame} {snippet}")
            sys.stdout.flush()
            time.sleep(0.1)
        
        # Clear the screen again for the main banner
        console.clear()
        
        # Display the ASCII art with a border and animated style
        panel = Panel(
            supernova_art,
            style=f"bold {theme_color('primary')}",
            border_style=theme_color("secondary"),
            box=ROUNDED,
            title="✨ Welcome to SuperNova ✨",
            title_align="center",
            subtitle="🚀 Your AI Coding Assistant",
            subtitle_align="center"
        )
        console.print(panel)
        
        # Animated tagline with typing effect
        animated_print("AI-powered development assistant within the terminal", delay=0.02)
        time.sleep(0.3)
        
        # Display version and info in a styled box
        info_panel = Panel(
            f"Type your questions or commands below.\nType '[bold]exit[/bold]' or '[bold]quit[/bold]' to end the session.\nUse [bold]Ctrl+C[/bold] to interrupt at any time.",
            title="📋 Instructions",
            title_align="left",
            border_style=theme_color("info"),
            box=ROUNDED,
            padding=(1, 2)
        )
        console.print(info_panel)
        
        # Show a few more flying elements at the bottom
        for i in range(5):  # Show 5 more frames
            frame = rocket_frames[(i + 5) % len(rocket_frames)]
            sys.stdout.write("\r" + " " * 80 + "\r")  # Clear line
            sys.stdout.write(f"\r{frame}")
            sys.stdout.flush()
            time.sleep(0.1)
        
        # Clear the last line
        sys.stdout.write("\r" + " " * 80 + "\r")
        sys.stdout.flush()
        
    except Exception as e:
        # Fallback to simple banner if there's an error
        console.print("\n=== SUPERNOVA ===")
        console.print("AI-powered development assistant within the terminal")
        console.print("Type 'exit' or 'quit' to end the session. Use Ctrl+C to interrupt.\n")

def display_tool_execution(tool_name: str, args: Dict[str, Any]) -> None:
    """
    Display tool execution with animation.
    
    Args:
        tool_name: Name of the tool being executed
        args: Tool arguments
    """
    try:
        # Create a panel with tool information
        tool_panel = Panel(
            f"[bold]Tool:[/bold] {tool_name}\n\n[bold]Arguments:[/bold]\n{args}",
            title="Tool Execution",
            title_align="left",
            border_style=theme_color("primary"),
            padding=(1, 2)
        )
        
        console.print(tool_panel)
        
        # Use a simple animation instead of a progress bar to avoid nested live displays
        console.print(f"[{theme_color('primary')}]Executing {tool_name}...[/{theme_color('primary')}]")
        
        # Simple spinner animation
        spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        for i in range(20):  # Show 20 frames of animation
            sys.stdout.write(f"\r{spinner_chars[i % len(spinner_chars)]} Processing...")
            sys.stdout.flush()
            time.sleep(0.05)
            
        # Clear the line when done
        sys.stdout.write("\r" + " " * 20 + "\r")
        sys.stdout.flush()
        
        console.print(f"[{theme_color('success')}]Tool execution completed[/{theme_color('success')}]")
    except Exception as e:
        # Fallback to simple message if animation fails
        console.print(f"Executing {tool_name}...")
        time.sleep(1)
        console.print("Tool execution completed")

def format_rich_objects(obj):
    """
    Format rich objects to string representation.
    
    Args:
        obj: Any object, possibly a rich renderable
        
    Returns:
        String representation of the object
    """
    from rich.markdown import Markdown
    from rich.syntax import Syntax
    from rich.console import Console
    
    # Create a string IO console to render the object
    from io import StringIO
    string_console = Console(file=StringIO(), width=80)
    
    try:
        # Render rich objects to string
        if isinstance(obj, (Markdown, Syntax)):
            string_console.print(obj)
            return string_console.file.getvalue()
        elif hasattr(obj, "__rich_console__"):
            string_console.print(obj)
            return string_console.file.getvalue()
        else:
            return str(obj)
    except Exception:
        # Fall back to string representation
        return str(obj)

def display_response(content: str, role: str = "assistant") -> None:
    """
    Display a response with appropriate formatting in a box.
    
    Args:
        content: Response content
        role: Role of the responder (assistant, system, etc.)
    """
    # Define icons and colors based on role
    if role == "assistant":
        color = theme_color("primary")
        icon = "🤖"
        title = "SuperNova AI"
        border_style = theme_color("primary")
        box_style = f"dim {theme_color('primary')}"
    elif role == "system":
        color = theme_color("info")
        icon = "🖥️"
        title = "System"
        border_style = theme_color("info")
        box_style = f"dim {theme_color('info')}"
    elif role == "user":
        color = theme_color("secondary")
        icon = "👤"
        title = "You"
        border_style = theme_color("secondary")
        box_style = f"dim {theme_color('secondary')}"
    elif role == "tool":
        color = theme_color("highlight")
        icon = "🔧"
        title = "Tool"
        border_style = theme_color("highlight")
        box_style = f"dim {theme_color('highlight')}"
    else:
        color = "white"
        icon = "📝"
        title = role.capitalize()
        border_style = "white"
        box_style = "dim white"
    
    # Import rich objects
    from rich.markdown import Markdown
    from rich.syntax import Syntax
    
    # Handle rich objects in content
    if isinstance(content, (Markdown, Syntax, Panel, Text)):
        content = format_rich_objects(content)
    elif hasattr(content, "__rich_console__"):
        content = format_rich_objects(content)
    
    # Ensure content is a string for further processing
    if not isinstance(content, str):
        content = str(content)
    
    # Process markdown in the content
    try:
        # Extract code blocks for syntax highlighting
        import re
        code_blocks = re.findall(r'```(\w*)\n(.*?)```', content, re.DOTALL)
        
        if code_blocks:
            # Replace code blocks with placeholders
            placeholder_map = {}
            for i, (lang, code) in enumerate(code_blocks):
                placeholder = f"__CODE_BLOCK_{i}__"
                placeholder_map[placeholder] = (lang.strip() or "python", code.strip())
                content = content.replace(f"```{lang}\n{code}```", placeholder)
            
            # Split by placeholders
            parts = []
            for part in re.split(r'(__CODE_BLOCK_\d+__)', content):
                if part in placeholder_map:
                    lang, code = placeholder_map[part]
                    parts.append(Syntax(code, lang, theme="monokai", line_numbers=True))
                else:
                    if part.strip():
                        parts.append(Markdown(part))
            
            # Create a layout for the panel content
            panel_content = ""
            for part in parts:
                if isinstance(part, Syntax):
                    # For code blocks, we'll add them directly to the panel
                    panel_content += f"\n{str(part)}\n"
                else:
                    # For markdown, convert to string
                    panel_content += str(part)
            
            # Create a panel with the content
            panel = Panel(
                panel_content,
                title=f"{icon} {title}",
                title_align="left",
                border_style=border_style,
                box=ROUNDED,
                padding=(1, 2),
                style=box_style
            )
            try:
                console.print(panel)
            except Exception as e:
                # If the panel couldn't be rendered, fallback to plain text
                console.print(f"{icon} {title}: {content}")
        else:
            # No code blocks, create a panel with markdown content
            panel = Panel(
                Markdown(content),
                title=f"{icon} {title}",
                title_align="left",
                border_style=border_style,
                box=ROUNDED,
                padding=(1, 2),
                style=box_style
            )
            try:
                console.print(panel)
            except Exception as e:
                # If the panel couldn't be rendered, fallback to plain text
                console.print(f"{icon} {title}: {content}")
    except Exception as e:
        # Fallback to simple panel if markdown processing fails
        panel = Panel(
            content,
            title=f"{icon} {title}",
            title_align="left",
            border_style=border_style,
            box=ROUNDED,
            padding=(1, 2),
            style=box_style
        )
        try:
            console.print(panel)
        except Exception as e:
            # If all else fails, just print the content as plain text
            console.print(f"{icon} {title}: {content}")

@contextmanager
def animated_status(message: str) -> None:
    """
    Context manager for displaying an animated status message.
    
    Note: Be careful not to nest this with other live displays as Rich only
    supports one live display at a time.
    
    Args:
        message: Status message to display
    """
    try:
        with console.status(message, spinner="dots") as status:
            yield status
    except Exception as e:
        # Fallback to simple print if status fails (likely due to nested live displays)
        console.print(message)
        yield None

def create_progress_bar(description: str = "Processing") -> Progress:
    """
    Create a rich progress bar.
    
    Note: Be careful not to nest this with other live displays as Rich only
    supports one live display at a time.
    
    Args:
        description: Description for the progress bar
        
    Returns:
        Progress object
    """
    try:
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        )
    except Exception as e:
        # If we can't create a progress bar (likely due to nested live displays),
        # log the error and return a dummy progress object
        console.print(f"Warning: Could not create progress bar: {str(e)}")
        
        # Create a dummy progress class that does nothing but prevents errors
        class DummyProgress:
            def __enter__(self):
                console.print(description)
                return self
                
            def __exit__(self, exc_type, exc_val, exc_tb):
                pass
                
            def add_task(self, description, total=100):
                return 0
                
            def update(self, task_id, **kwargs):
                pass
        
        return DummyProgress()

def display_command_result(command: str, result: str, success: bool = True) -> None:
    """
    Display command execution result with animation.
    
    Args:
        command: Command that was executed
        result: Command result
        success: Whether the command was successful
    """
    # Determine color based on success
    color = theme_color("success") if success else theme_color("error")
    status = "✅ Success" if success else "❌ Failed"
    
    # Create a panel with command information
    command_panel = Panel(
        f"[bold]Command:[/bold] {command}\n\n[bold]Result:[/bold]\n{result}",
        title=f"Command Execution - {status}",
        title_align="left",
        border_style=color,
        padding=(1, 2)
    )
    
    console.print(command_panel)

def display_thinking_animation(duration: float = 1.0) -> None:
    """
    Display an enhanced thinking animation with brain activity visualization.
    
    Args:
        duration: Duration of the animation in seconds
    """
    try:
        # More elaborate thinking animation with brain activity
        thinking_frames = [
            "🧠 ⚡ Thinking...",  # Fixed the missing character
            "🧠 ✨ Thinking...",
            "🧠 💭 Thinking...",
            "🧠 💡 Thinking...",
            "🧠 🔄 Thinking...",
            "🧠 🔍 Thinking...",
            "🧠 📊 Thinking...",
            "🧠 🔮 Thinking..."
        ]
        
        # Brain activity patterns (simulating neural activity)
        brain_patterns = [
            "▁▂▃▄▅▆▇█▇▆▅▄▃▂▁",
            "▁▁▂▂▃▃▄▄▅▅▆▆▇▇██▇▇▆▆▅▅▄▄▃▃▂▂▁▁",
            "▂▃▅▇█▇▅▃▂▂▃▅▇█▇▅▃▂",
            "▅▆▇█▇▆▅▄▃▂▁▂▃▄▅▆▇█▇▆▅",
            "▁▂▄▆█▆▄▂▁▁▂▄▆█▆▄▂▁"
        ]
        
        # Timer display
        start_time = time.time()
        end_time = start_time + duration
        
        # Create a panel for the thinking animation
        panel_width = 60
        
        # Use Rich's Live display for smooth updates
        with Live("", refresh_per_second=10, transient=True) as live:
            while time.time() < end_time:
                elapsed = time.time() - start_time
                remaining = max(0, duration - elapsed)
                
                # Select frame and pattern based on time
                frame_idx = int(elapsed * 8) % len(thinking_frames)
                pattern_idx = int(elapsed * 5) % len(brain_patterns)
                
                # Create the panel content
                frame = thinking_frames[frame_idx]
                pattern = brain_patterns[pattern_idx]
                
                # Format timer
                timer = f"{elapsed:.1f}s / {duration:.1f}s"
                
                # Create panel with thinking animation
                panel = Panel(
                    f"{frame}\n\n{pattern}\n\n⏱️ {timer}",
                    title="🤔 Processing",
                    title_align="left",
                    border_style=theme_color("primary"),
                    box=ROUNDED,
                    width=panel_width,
                    padding=(1, 2)
                )
                
                # Update the live display
                live.update(panel)
                
                time.sleep(0.1)
        
    except Exception as e:
        # Fallback to simple message if animation fails
        console.print(f"[{theme_color('primary')}]🧠 Thinking...[/{theme_color('primary')}]")
        time.sleep(duration)

def fade_in_text(text: str, delay: float = 0.05) -> None:
    """
    Display text with a fade-in effect.
    
    Args:
        text: Text to display
        delay: Delay between characters in seconds
    """
    for i in range(len(text) + 1):
        sys.stdout.write("\r" + text[:i])
        sys.stdout.flush()
        time.sleep(delay)
    print()

def display_chat_input_prompt() -> None:
    """Display an animated prompt for chat input."""
    prompt_text = "You: "
    fade_in_text(prompt_text, delay=0.01)
    
def display_generating_animation(duration: float = 2.0) -> None:
    """
    Display an animation for the generating response state with a timer.
    
    Args:
        duration: Duration of the animation in seconds
    """
    try:
        # Generation frames with different icons
        gen_frames = [
            "🔄 Generating response...",
            "⚙️ Generating response...",
            "🔍 Generating response...",
            "💬 Generating response...",
            "📝 Generating response...",
            "🔮 Generating response...",
            "✨ Generating response...",
            "📊 Generating response..."
        ]
        
        # Progress patterns
        progress_patterns = [
            "[▓▓▓▓▓▓▓▓▓▓          ] 50%",
            "[▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓     ] 75%",
            "[▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓] 100%",
            "[▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓    ] 80%",
            "[▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓  ] 90%",
            "[▓▓▓▓▓▓▓▓             ] 40%",
            "[▓▓▓▓▓▓▓▓▓▓▓▓▓       ] 65%",
            "[▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓   ] 85%"
        ]
        
        # Timer display
        start_time = time.time()
        end_time = start_time + duration
        
        # Create a panel for the generation animation
        panel_width = 60
        
        # Use Rich's Live display for smooth updates
        with Live("", refresh_per_second=10, transient=True) as live:
            while time.time() < end_time:
                elapsed = time.time() - start_time
                remaining = max(0, duration - elapsed)
                
                # Select frame and pattern based on time
                frame_idx = int(elapsed * 8) % len(gen_frames)
                pattern_idx = int(elapsed * 5) % len(progress_patterns)
                
                # Create the panel content
                frame = gen_frames[frame_idx]
                pattern = progress_patterns[pattern_idx]
                
                # Format timer
                timer = f"{elapsed:.1f}s elapsed"
                
                # Create panel with generation animation
                panel = Panel(
                    f"{frame}\n\n{pattern}\n\n⏱️ {timer}",
                    title="🤖 SuperNova AI",
                    title_align="left",
                    border_style=theme_color("secondary"),
                    box=ROUNDED,
                    width=panel_width,
                    padding=(1, 2)
                )
                
                # Update the live display
                live.update(panel)
                
                time.sleep(0.1)
        
    except Exception as e:
        # Fallback to simple message if animation fails
        console.print(f"[{theme_color('secondary')}]🤖 Generating response...[/{theme_color('secondary')}]")
        time.sleep(duration)

def display_tool_confirmation(tool_name: str, args: Dict[str, Any]) -> None:
    """
    Display a confirmation dialog for tool execution with animation.
    
    Args:
        tool_name: Name of the tool being executed
        args: Tool arguments
        
    Returns:
        True if confirmed, False otherwise
    """
    # Create a panel with tool information
    tool_panel = Panel(
        f"[bold]Tool:[/bold] {tool_name}\n\n[bold]Arguments:[/bold]\n{args}",
        title="🔧 Confirm Tool Execution",
        title_align="left",
        border_style=theme_color("warning"),
        box=ROUNDED,
        padding=(1, 2)
    )
    
    console.print(tool_panel)