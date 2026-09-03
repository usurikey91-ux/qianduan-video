const fs = require('node:fs');
const path = require('node:path');
const https = require('node:https');

const rootDir = path.resolve(__dirname, '..');
const toolsDir = path.join(rootDir, 'tools');
const target = path.join(toolsDir, 'yt-dlp.exe');
const downloadUrl = 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe';

fs.mkdirSync(toolsDir, { recursive: true });
fs.mkdirSync(path.join(rootDir, 'downloads'), { recursive: true });

function download(url, destination, redirects = 0) {
  return new Promise((resolve, reject) => {
    if (redirects > 8) {
      reject(new Error('Too many redirects while downloading yt-dlp.'));
      return;
    }

    const request = https.get(url, {
      headers: { 'User-Agent': 'video-jiexi-setup' }
    }, (response) => {
      if (response.statusCode >= 300 && response.statusCode < 400 && response.headers.location) {
        response.resume();
        const nextUrl = new URL(response.headers.location, url).toString();
        resolve(download(nextUrl, destination, redirects + 1));
        return;
      }

      if (response.statusCode !== 200) {
        response.resume();
        reject(new Error(`yt-dlp download failed with HTTP ${response.statusCode}.`));
        return;
      }

      const temporary = `${destination}.download`;
      const file = fs.createWriteStream(temporary);
      response.pipe(file);
      file.on('finish', () => {
        file.close(() => {
          fs.renameSync(temporary, destination);
          resolve();
        });
      });
      file.on('error', reject);
    });
    request.setTimeout(120_000, () => request.destroy(new Error('yt-dlp download timed out.')));
    request.on('response', () => request.setTimeout(0));
    request.on('error', reject);
  });
}

async function downloadWithRetry(url, destination, attempts = 3) {
  let lastError;
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      await download(url, destination);
      return;
    } catch (error) {
      lastError = error;
      fs.rmSync(`${destination}.download`, { force: true });
      if (attempt < attempts) {
        console.warn(`yt-dlp download attempt ${attempt} failed; retrying...`);
        await new Promise((resolve) => setTimeout(resolve, 1500 * attempt));
      }
    }
  }
  throw lastError;
}

(async () => {
  if (fs.existsSync(target) && fs.statSync(target).size > 1_000_000) {
    console.log(`yt-dlp is already installed: ${target}`);
    return;
  }

  console.log('Downloading the latest yt-dlp...');
  await downloadWithRetry(downloadUrl, target);
  console.log(`Installed yt-dlp: ${target}`);
})().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
