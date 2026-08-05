import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';

// Lesson data structure
interface Lesson {
    title: string;
    domain: string;
    tags: string[];
    status: string;
    path: string;
    content: string;
}

// Tree data provider for sidebar
class LessonTreeProvider implements vscode.TreeDataProvider<LessonItem> {
    private _onDidChangeTreeData: vscode.EventEmitter<LessonItem | undefined | null | void> = new vscode.EventEmitter<LessonItem | undefined | null | void>();
    readonly onDidChangeTreeData: vscode.Event<LessonItem | undefined | null | void> = this._onDidChangeTreeData.event;

    private lessons: Lesson[] = [];
    private repoRoot: string;

    constructor(repoRoot: string) {
        this.repoRoot = repoRoot;
        this.loadLessons();
    }

    refresh(): void {
        this.loadLessons();
        this._onDidChangeTreeData.fire();
    }

    getTreeItem(element: LessonItem): vscode.TreeItem {
        return element;
    }

    getChildren(element?: LessonItem): Thenable<LessonItem[]> {
        if (!element) {
            // Root level - show domains
            const domains = [...new Set(this.lessons.map(l => l.domain || 'uncategorized'))];
            return Promise.resolve(domains.map(d => new LessonItem(
                d,
                vscode.TreeItemCollapsibleState.Collapsed,
                'domain'
            )));
        }

        if (element.contextValue === 'domain') {
            // Show lessons in this domain
            const domainLessons = this.lessons.filter(l => (l.domain || 'uncategorized') === element.label);
            return Promise.resolve(domainLessons.map(l => new LessonItem(
                l.title,
                vscode.TreeItemCollapsibleState.None,
                'lesson',
                l
            )));
        }

        return Promise.resolve([]);
    }

    private loadLessons(): void {
        const lessonsDir = path.join(this.repoRoot, 'lessons');
        this.lessons = [];

        for (const subdir of ['core', 'contrib']) {
            const dir = path.join(lessonsDir, subdir);
            if (!fs.existsSync(dir)) continue;

            const files = fs.readdirSync(dir).filter(f => f.endsWith('.md') && f !== 'index.md');
            for (const file of files) {
                const filePath = path.join(dir, file);
                const content = fs.readFileSync(filePath, 'utf-8');

                // Parse frontmatter
                const fmMatch = content.match(/^---\s*\n(.*?)\n---/s);
                if (!fmMatch) continue;

                const fm: any = {};
                for (const line of fmMatch[1].split('\n')) {
                    const colonIdx = line.indexOf(':');
                    if (colonIdx > 0) {
                        const key = line.substring(0, colonIdx).trim();
                        const val = line.substring(colonIdx + 1).trim().replace(/^["']|["']$/g, '');
                        fm[key] = val;
                    }
                }

                this.lessons.push({
                    title: fm.title || file.replace('.md', ''),
                    domain: fm.domain || '',
                    tags: fm.tags ? (typeof fm.tags === 'string' ? fm.tags.split(',').map((t: string) => t.trim()) : fm.tags) : [],
                    status: fm.status || '',
                    path: filePath,
                    content: content.substring(fmMatch[0].length).trim().substring(0, 200),
                });
            }
        }
    }

    search(query: string): Lesson[] {
        const q = query.toLowerCase();
        return this.lessons.filter(l =>
            l.title.toLowerCase().includes(q) ||
            l.domain.toLowerCase().includes(q) ||
            l.tags.some(t => t.toLowerCase().includes(q)) ||
            l.content.toLowerCase().includes(q)
        );
    }
}

// Tree item
class LessonItem extends vscode.TreeItem {
    public lesson?: Lesson;

    constructor(
        label: string,
        collapsibleState: vscode.TreeItemCollapsibleState,
        contextValue: string,
        lesson?: Lesson
    ) {
        super(label, collapsibleState);
        this.contextValue = contextValue;
        this.lesson = lesson;

        if (contextValue === 'lesson' && lesson) {
            this.description = lesson.domain;
            this.tooltip = lesson.title;
            this.command = {
                command: 'misakanet.openLesson',
                title: 'Open Lesson',
                arguments: [lesson]
            };
            this.iconPath = new vscode.ThemeIcon('file-text');
        } else if (contextValue === 'domain') {
            this.iconPath = new vscode.ThemeIcon('folder');
        }
    }
}

// Extension activation
export function activate(context: vscode.ExtensionContext) {
    // Find repo root
    const workspaceFolders = vscode.workspace.workspaceFolders;
    let repoRoot = '';

    if (workspaceFolders) {
        // Look for lessons directory
        for (const folder of workspaceFolders) {
            const lessonsDir = path.join(folder.uri.fsPath, 'lessons');
            if (fs.existsSync(lessonsDir)) {
                repoRoot = folder.uri.fsPath;
                break;
            }
        }
    }

    if (!repoRoot) {
        vscode.window.showWarningMessage('MisakaNet: No lessons directory found in workspace');
        return;
    }

    // Create tree provider
    const treeProvider = new LessonTreeProvider(repoRoot);
    vscode.window.registerTreeDataProvider('misakanet-lessons', treeProvider);

    // Search command
    context.subscriptions.push(
        vscode.commands.registerCommand('misakanet.search', async () => {
            const query = await vscode.window.showInputBox({
                prompt: 'Search MisakaNet lessons',
                placeHolder: 'e.g. pip timeout, database locked, DCO',
            });

            if (!query) return;

            const results = treeProvider.search(query);
            if (results.length === 0) {
                vscode.window.showInformationMessage(`No lessons found for "${query}"`);
                return;
            }

            // Show results in quick pick
            const items = results.map(l => ({
                label: l.title,
                description: l.domain,
                detail: l.tags.join(', '),
                lesson: l,
            }));

            const selected = await vscode.window.showQuickPick(items, {
                placeHolder: `${results.length} lessons found`,
            });

            if (selected) {
                openLesson(selected.lesson);
            }
        })
    );

    // List command
    context.subscriptions.push(
        vscode.commands.registerCommand('misakanet.list', async () => {
            const lessons = treeProvider.search('');
            const items = lessons.map(l => ({
                label: l.title,
                description: l.domain,
                detail: l.tags.join(', '),
                lesson: l,
            }));

            const selected = await vscode.window.showQuickPick(items, {
                placeHolder: `${lessons.length} lessons available`,
            });

            if (selected) {
                openLesson(selected.lesson);
            }
        })
    );

    // Open lesson command
    context.subscriptions.push(
        vscode.commands.registerCommand('misakanet.openLesson', (lesson: Lesson) => {
            openLesson(lesson);
        })
    );

    // Refresh command
    context.subscriptions.push(
        vscode.commands.registerCommand('misakanet.refresh', () => {
            treeProvider.refresh();
        })
    );

    vscode.window.showInformationMessage(`MisakaNet: ${treeProvider.search('').length} lessons loaded`);
}

function openLesson(lesson: Lesson) {
    vscode.workspace.openTextDocument(lesson.path).then(doc => {
        vscode.window.showTextDocument(doc);
    });
}

export function deactivate() {}
