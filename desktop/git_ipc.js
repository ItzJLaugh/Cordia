function registerGitIpcHandlers({ ipcMain, dialog, gitSkills }) {
  ipcMain.handle('cordia-desktop:git-preview', async (event, repositoryId, operation) => {
    const preview = await gitSkills.preview(repositoryId, operation);
    const response = await dialog.showMessageBox(event.sender.getOwnerBrowserWindow(), {
      type: 'warning',
      buttons: ['Cancel', 'Continue'],
      defaultId: 0,
      cancelId: 0,
      noLink: true,
      message: `Confirm Git ${preview.operation}`,
      detail: `Branch: ${preview.branch}`,
    });
    gitSkills.approvals.decide(preview.approval.id, response.response === 1);
    return preview;
  });
  ipcMain.handle('cordia-desktop:git-execute', (_event, approvalId) => gitSkills.execute(approvalId));
}

module.exports = { registerGitIpcHandlers };
