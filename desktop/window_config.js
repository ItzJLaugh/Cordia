const path = require('node:path');

const CLOUD_ORIGIN = 'https://cordiacode.com';

function cloudUrl(environment = process.env) {
  const configured = environment.CORDIA_DESKTOP_URL;
  if (!configured) return CLOUD_ORIGIN;

  const url = new URL(configured);
  const isCordiaCloud = url.origin === CLOUD_ORIGIN;
  const isLocalPreview = url.protocol === 'http:' && ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
  if (!isCordiaCloud && !isLocalPreview) {
    throw new Error('CORDIA_DESKTOP_URL must be https://cordiacode.com or a localhost URL.');
  }
  return url.toString().replace(/\/$/, '');
}

function buildWindowOptions() {
  return {
    width: 1440,
    height: 960,
    minWidth: 1024,
    minHeight: 700,
    title: 'Cordia',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  };
}

module.exports = { buildWindowOptions, cloudUrl };
