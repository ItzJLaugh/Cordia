const { app, BrowserWindow, dialog, ipcMain } = require('electron');
const { execFile } = require('node:child_process');
const gitAdapter = require('./git_adapter');
const { GitSkills } = require('./git_skills');
const { registerGitIpcHandlers } = require('./git_ipc');
const { LocalApprovals } = require('./local_approvals');
const { discoverRepository } = require('./local_repository');
const { RepositoryRegistry } = require('./repository_registry');
const { pickRepository } = require('./repository_picker');
const { buildWindowOptions, cloudUrl } = require('./window_config');

const repositoryRegistry = new RepositoryRegistry();
const gitSkills = new GitSkills({
  registry: repositoryRegistry,
  adapter: {
    status: (selectedPath) => gitAdapter.status(selectedPath, execFile),
    run: (selectedPath, operation) => gitAdapter.run(selectedPath, operation, execFile),
  },
  approvals: new LocalApprovals(),
});

function runtimeInfo() {
  return { platform: process.platform, version: app.getVersion() };
}

function createWindow() {
  const window = new BrowserWindow(buildWindowOptions());
  window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  window.loadURL(cloudUrl());
  return window;
}

ipcMain.handle('cordia-desktop:runtime-info', () => runtimeInfo());
ipcMain.handle('cordia-desktop:pick-repository', () => pickRepository(
  dialog,
  discoverRepository,
  (metadata, selectedPath) => repositoryRegistry.register(metadata, selectedPath),
));
ipcMain.handle('cordia-desktop:git-status', (_event, repositoryId) => gitSkills.status(repositoryId));
ipcMain.handle('cordia-desktop:git-wait', (_event, repositoryId, condition) => gitSkills.wait(repositoryId, condition));
registerGitIpcHandlers({ ipcMain, dialog, gitSkills });

app.whenReady().then(() => {
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

module.exports = { createWindow, runtimeInfo };
