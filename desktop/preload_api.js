function desktopApi(ipcRenderer) {
  return Object.freeze({
    getRuntimeInfo: () => ipcRenderer.invoke('cordia-desktop:runtime-info'),
    pickRepository: () => ipcRenderer.invoke('cordia-desktop:pick-repository'),
    gitStatus: (repositoryId) => ipcRenderer.invoke('cordia-desktop:git-status', repositoryId),
    gitWait: (repositoryId, condition) => ipcRenderer.invoke('cordia-desktop:git-wait', repositoryId, condition),
    gitPreview: (repositoryId, operation) => ipcRenderer.invoke('cordia-desktop:git-preview', repositoryId, operation),
    gitExecute: (approvalId) => ipcRenderer.invoke('cordia-desktop:git-execute', approvalId),
  });
}

module.exports = { desktopApi };
