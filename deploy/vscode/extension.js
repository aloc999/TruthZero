// TRUTHZERO Swarm VS Code extension (beta).
// Runs `truthzero scan --swarm` in a terminal and opens the SARIF output.
const vscode = require('vscode');
const cp = require('child_process');

function runScan() {
  const target = vscode.window.activeTextEditor
    ? vscode.window.activeTextEditor.document.fileName
    : '';
  const input = vscode.window.showInputBox({
    prompt: 'Target for swarm scan (must be in scope)',
    value: target
  });
  input.then(t => {
    if (!t) return;
    const term = vscode.window.createTerminal('truthzero-swarm');
    term.show();
    term.sendText(`truthzero scan "${t}" --scope "${t}" --swarm`);
  });
}

function showFindings() {
  vscode.window.showOpenDialog({
    filters: { SARIF: ['sarif'] }, canSelectMany: false
  }).then(files => {
    if (files && files[0]) vscode.window.showTextDocument(files[0]);
  });
}

function activate(context) {
  context.subscriptions.push(
    vscode.commands.registerCommand('truthzero.scan', runScan),
    vscode.commands.registerCommand('truthzero.showFindings', showFindings)
  );
}

function deactivate() {}

module.exports = { activate, deactivate };
