document.getElementById('save').addEventListener('click', async () => {
  const baseUrl = document.getElementById('baseUrl').value.trim();
  const deviceToken = document.getElementById('deviceToken').value.trim();
  if (!baseUrl) {
    document.getElementById('status').textContent = '请填写后端地址';
    return;
  }
  await chrome.storage.local.set({ baseUrl: baseUrl.replace(/\/$/, ''), deviceToken });
  document.getElementById('status').textContent = '已保存';
  setTimeout(() => { document.getElementById('status').textContent = ''; }, 2000);
});

chrome.storage.local.get(['baseUrl', 'deviceToken'], (r) => {
  if (r.baseUrl) document.getElementById('baseUrl').value = r.baseUrl;
  if (r.deviceToken) document.getElementById('deviceToken').value = r.deviceToken;
});
