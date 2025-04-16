// SuperNova VS Code Extension - Error Handler
// This file provides error handling utilities for the extension

const vscode = require('vscode');

/**
 * Error types for the SuperNova extension
 */
const ErrorType = {
    CONNECTION: 'connection',
    CONFIGURATION: 'configuration',
    EXECUTION: 'execution',
    AUTHENTICATION: 'authentication',
    UNKNOWN: 'unknown'
};

/**
 * Handle errors in the SuperNova extension
 * @param {Error} error - The error object
 * @param {string} type - The type of error (from ErrorType)
 * @param {boolean} showNotification - Whether to show a notification to the user
 * @param {vscode.OutputChannel} outputChannel - The output channel for logging
 */
function handleError(error, type = ErrorType.UNKNOWN, showNotification = true, outputChannel = null) {
    // Log the error
    console.error(`SuperNova Error (${type}):`, error);
    
    // Log to output channel if available
    if (outputChannel) {
        outputChannel.appendLine(`[ERROR] ${new Date().toISOString()} - ${type.toUpperCase()}: ${error.message}`);
        if (error.stack) {
            outputChannel.appendLine(error.stack);
        }
    }
    
    // Show notification based on error type
    if (showNotification) {
        switch (type) {
            case ErrorType.CONNECTION:
                vscode.window.showErrorMessage(
                    `SuperNova: Connection error - ${error.message}`,
                    'Retry', 'Settings'
                ).then(selection => {
                    if (selection === 'Settings') {
                        vscode.commands.executeCommand('workbench.action.openSettings', 'supernova');
                    } else if (selection === 'Retry') {
                        // TODO: Implement retry logic based on the failed operation
                    }
                });
                break;
                
            case ErrorType.CONFIGURATION:
                vscode.window.showErrorMessage(
                    `SuperNova: Configuration error - ${error.message}`,
                    'Open Settings'
                ).then(selection => {
                    if (selection === 'Open Settings') {
                        vscode.commands.executeCommand('workbench.action.openSettings', 'supernova');
                    }
                });
                break;
                
            case ErrorType.EXECUTION:
                vscode.window.showErrorMessage(`SuperNova: Command execution error - ${error.message}`);
                break;
                
            case ErrorType.AUTHENTICATION:
                vscode.window.showErrorMessage(
                    `SuperNova: Authentication error - ${error.message}`,
                    'Configure API Key'
                ).then(selection => {
                    if (selection === 'Configure API Key') {
                        // TODO: Implement API key configuration UI
                        vscode.commands.executeCommand('workbench.action.openSettings', 'supernova');
                    }
                });
                break;
                
            default:
                vscode.window.showErrorMessage(`SuperNova: An error occurred - ${error.message}`);
                break;
        }
    }
}

/**
 * Create and configure an output channel for logging
 * @returns {vscode.OutputChannel} The configured output channel
 */
function createOutputChannel() {
    const channel = vscode.window.createOutputChannel('SuperNova');
    channel.appendLine(`[INFO] ${new Date().toISOString()} - SuperNova extension initialized`);
    return channel;
}

module.exports = {
    ErrorType,
    handleError,
    createOutputChannel
}; 