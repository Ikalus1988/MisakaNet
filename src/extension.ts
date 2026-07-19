import * as vscode from 'vscode';
import { searchLessons } from './search';

export function activate(context: vscode.ExtensionContext) {
    let disposable = vscode.commands.registerCommand('misakanet.searchLessons', () => {
        vscode.window.showInputBox({ prompt: 'Enter the search term' }).then(searchTerm => {
            if (searchTerm) {
                const lessons = searchLessons(searchTerm);
                showResults(lessons);
            }
        });
    });

    context.subscriptions.push(disposable);
}

function showResults(lessons: string[]) {
    const quickPickItems = lessons.map(lesson => ({ label: lesson }));
    const quickPick = vscode.window.createQuickPick();
    quickPick.items = quickPickItems;
    quickPick.onDidChangeSelection(selection => {
        if (selection[0]) {
            vscode.workspace.openTextDocument(vscode.Uri.file(selection[0].label)).then(doc => {
                vscode.window.showTextDocument(doc);
            });
        }
    });
    quickPick.show();
}

export function deactivate() {}
