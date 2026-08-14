const { contextBridge, ipcRenderer } = require('electron');
const { desktopApi } = require('./preload_api');

contextBridge.exposeInMainWorld('cordiaDesktop', desktopApi(ipcRenderer));
