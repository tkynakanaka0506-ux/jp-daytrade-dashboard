// sw.js — 最小構成のService Worker。
//
// news.jsonは「今アクティブなニュース」のスナップショットであり、
// キャッシュして古い記事を表示し続けることは避けたい(CLAUDE.mdの
// 「取得できなかったときは前回値を使わない」という方針と同じ理由)。
// そのため今はオフラインキャッシュを一切行わず、fetchはネットワークへ
// そのまま素通しするだけにしてある。
//
// 今回追加した目的は「PWAとしてインストール可能にする」ための最低条件
// （Service Workerの登録実績）を満たすことと、将来のPush通知に備えて
// pushイベントの受け口だけ用意しておくこと(GitHub Pages配信=HTTPSなので
// 姉妹プロジェクトの株ボードと違い、将来実際に送信できる)。
self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', () => {
  // 何もしない = ブラウザの通常のネットワーク処理に任せる。
});

self.addEventListener('push', (event) => {
  if (!event.data) return;
  let payload;
  try {
    payload = event.data.json();
  } catch (e) {
    payload = { title: '重要ニュース', body: event.data.text() };
  }
  event.waitUntil(
    self.registration.showNotification(payload.title ?? '重要ニュース', {
      body: payload.body ?? '',
      icon: 'icon-192.png',
      badge: 'icon-192.png',
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(self.clients.openWindow(event.notification.data?.url ?? '.'));
});
