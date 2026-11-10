#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

const prefix = process.argv[2];
if (!prefix) throw new Error('OpenCLI npm prefix is required');
const file = path.join(prefix, 'node_modules', '@jackwener', 'opencli', 'clis', 'douyin', 'user-videos.js');
let source = fs.readFileSync(file, 'utf8');
const columns = "    columns: [\n        'index', 'aweme_id', 'title', 'duration', 'published_at', 'url',\n        'digg_count', 'comment_count', 'collect_count', 'share_count',\n        'play_count', 'play_url', 'top_comments',\n    ],";
const oldColumns = "    columns: ['index', 'aweme_id', 'title', 'duration', 'digg_count', 'play_url', 'top_comments'],";
if (source.includes(oldColumns)) source = source.replace(oldColumns, columns);
const oldMap = "            const playUrl = video.video?.play_addr?.url_list?.[0] ?? '';\n            return {\n                index: index + 1,\n                aweme_id: video.aweme_id,\n                title: video.desc ?? '',\n                duration: Math.round((video.video?.duration ?? 0) / 1000),\n                digg_count: video.statistics?.digg_count ?? 0,\n                play_url: playUrl,\n                top_comments: video.top_comments ?? [],\n            };";
const newMap = "            const playUrl = video.video?.play_addr?.url_list?.[0] ?? '';\n            const createTime = Number(video.create_time ?? video.public_time ?? 0);\n            const statistics = video.statistics ?? {};\n            return {\n                index: index + 1,\n                aweme_id: video.aweme_id,\n                title: video.desc ?? '',\n                duration: Math.round((video.video?.duration ?? 0) / 1000),\n                published_at: createTime > 0 ? new Date(createTime * 1000).toISOString() : '',\n                url: video.aweme_id ? 'https://www.douyin.com/video/' + video.aweme_id : '',\n                digg_count: statistics.digg_count ?? 0,\n                comment_count: statistics.comment_count ?? 0,\n                collect_count: statistics.collect_count ?? statistics.collects_count ?? 0,\n                share_count: statistics.share_count ?? 0,\n                play_count: statistics.play_count ?? 0,\n                play_url: playUrl,\n                top_comments: video.top_comments ?? [],\n            };";
if (source.includes(oldMap)) source = source.replace(oldMap, newMap);
if (!source.includes('author: { nickname:')) {
  source = source.replace("'play_count', 'play_url', 'top_comments',", "'play_count', 'play_url', 'top_comments', 'author',");
  source = source.replace(
    '                index: index + 1,',
    "                author: { nickname: video.author?.nickname ?? '' },\n                index: index + 1,"
  );
}
fs.writeFileSync(file, source);
console.log('Patched OpenCLI Douyin user-videos output');
const runtimeFile = path.join(prefix, 'node_modules', '@jackwener', 'opencli', 'dist', 'src', 'runtime.js');
const runtimeSource = fs.readFileSync(runtimeFile, 'utf8');
const originalSelection = 'if (site && isElectronApp(site))';
const cdpSelection = 'if (process.env.OPENCLI_CDP_ENDPOINT?.trim() || (site && isElectronApp(site)))';
if (!runtimeSource.includes(cdpSelection)) {
  if (!runtimeSource.includes(originalSelection)) {
    throw new Error('Unsupported OpenCLI browser routing; explicit CDP patch was not applied');
  }
  fs.writeFileSync(runtimeFile, runtimeSource.replace(originalSelection, cdpSelection));
}
console.log('Patched OpenCLI explicit CDP routing');
const bilibiliFile = path.join(prefix, 'node_modules', '@jackwener', 'opencli', 'clis', 'bilibili', 'utils.js');
if (fs.existsSync(bilibiliFile)) {
  let bilibiliSource = fs.readFileSync(bilibiliFile, 'utf8');
  const jsonReturn = 'return await res.json();';
  const marker = 'Bilibili non-JSON response: HTTP ';
  if (!bilibiliSource.includes(marker)) {
    if (bilibiliSource.split(jsonReturn).length !== 3) {
      throw new Error('Unsupported Bilibili response parser; HTTP diagnostics patch was not applied');
    }
    const diagnostic = endpoint => `const text = await res.text();
      try { return JSON.parse(text); } catch {
        throw new Error('Bilibili non-JSON response: HTTP ' + res.status + ' at ' + ${endpoint});
      }`;
    bilibiliSource = bilibiliSource.replace(jsonReturn, diagnostic("'nav'"));
    bilibiliSource = bilibiliSource.replace(jsonReturn, diagnostic('new URL(${urlJs}).pathname'));
    fs.writeFileSync(bilibiliFile, bilibiliSource);
  }
}

const bilibiliUserVideosFile = path.join(
  prefix,
  'node_modules',
  '@jackwener',
  'opencli',
  'clis',
  'bilibili',
  'user-videos.js'
);
if (fs.existsSync(bilibiliUserVideosFile)) {
  let userVideosSource = fs.readFileSync(bilibiliUserVideosFile, 'utf8');
  const fallbackMarker = 'WORKBENCH_BILIBILI_PUBLIC_SEARCH_FALLBACK_ON_412';
  const originalImport = "import { apiGet, payloadData, resolveUid } from './utils.js';";
  const patchedImport = "import { apiGet, payloadData, resolveUid, stripHtml } from './utils.js';";
  if (!userVideosSource.includes('stripHtml')) {
    if (!userVideosSource.includes(originalImport)) {
      throw new Error('Unsupported Bilibili user-videos imports; public search fallback was not applied');
    }
    userVideosSource = userVideosSource.replace(originalImport, patchedImport);
  }

  if (!userVideosSource.includes(fallbackMarker)) {
    const originalBlock = `        const payload = await apiGet(page, '/x/space/wbi/arc/search', {
            params: {
                mid: uid,
                pn: pageNum,
                ps: Math.min(Number(limit), 50),
                order,
            },
            signed: true,
        });
        const vlist = payloadData(payload)?.list?.vlist ?? [];
        return vlist.slice(0, Number(limit)).map((item, i) => ({
            rank: i + 1,
            title: item.title ?? '',
            plays: item.play ?? 0,
            likes: item.like ?? 0,
            date: item.created ? new Date(item.created * 1000).toISOString().slice(0, 10) : '',
            url: item.bvid ? \`https://www.bilibili.com/video/\${item.bvid}\` : '',
        }));`;
    const patchedBlock = `        let vlist;
        try {
            const payload = await apiGet(page, '/x/space/wbi/arc/search', {
                params: {
                    mid: uid,
                    pn: pageNum,
                    ps: Math.min(Number(limit), 50),
                    order,
                },
                signed: true,
            });
            vlist = (payloadData(payload)?.list?.vlist ?? []).slice(0, Number(limit));
        } catch (error) {
            // ${fallbackMarker}: use only Bilibili public search results, filtered by stable UID.
            const message = String(error?.message ?? error);
            const isArcSearch412 =
                message.includes('Bilibili non-JSON response: HTTP 412 at /x/space/wbi/arc/search');
            if (!isArcSearch412) throw error;

            const profile = await apiGet(page, '/x/web-interface/card', {
                params: { mid: uid },
            });
            const nickname = String(payloadData(profile)?.card?.name ?? '').trim();
            if (!nickname) throw error;

            const pageNumber = Math.max(1, Number(pageNum) || 1);
            const pageSize = Math.max(1, Number(limit) || 20);
            const wantedCount = pageNumber * pageSize;
            const maxSearchPages = Math.min(5, Math.max(2, Math.ceil(wantedCount / 4)));
            const byBvid = new Map();
            for (let searchPage = 1; searchPage <= maxSearchPages && byBvid.size < wantedCount; searchPage++) {
                let searchPayload;
                try {
                    searchPayload = await apiGet(page, '/x/web-interface/search/all/v2', {
                        params: { keyword: nickname, page: searchPage, order: order || 'pubdate' },
                    });
                } catch (fallbackError) {
                    if (byBvid.size === 0) throw fallbackError;
                    break;
                }
                const sections = payloadData(searchPayload)?.result;
                const videos = Array.isArray(sections)
                    ? sections
                        .filter((section) => section?.result_type === 'video' && Array.isArray(section.data))
                        .flatMap((section) => section.data)
                    : [];
                for (const video of videos) {
                    if (String(video?.mid ?? '') !== String(uid) || !video?.bvid) continue;
                    if (!byBvid.has(video.bvid)) byBvid.set(video.bvid, video);
                }
            }

            const publicVideos = [...byBvid.values()]
                .sort((left, right) => Number(right.pubdate ?? 0) - Number(left.pubdate ?? 0));
            if (publicVideos.length === 0) throw error;
            const offset = (pageNumber - 1) * pageSize;
            vlist = publicVideos.slice(offset, offset + pageSize);
        }

        return vlist.map((item, i) => {
            const publishedAt = Number(item.created ?? item.pubdate ?? 0);
            return {
                rank: i + 1,
                title: stripHtml(String(item.title ?? '')),
                plays: item.play ?? 0,
                likes: item.like ?? item.fav ?? 0,
                date: publishedAt > 0 ? new Date(publishedAt * 1000).toISOString().slice(0, 10) : '',
                url: item.bvid ? \`https://www.bilibili.com/video/\${item.bvid}\` : '',
            };
        });`;
    if (userVideosSource.split(originalBlock).length !== 2) {
      throw new Error('Unsupported Bilibili user-videos implementation; public search fallback was not applied');
    }
    userVideosSource = userVideosSource.replace(originalBlock, patchedBlock);
    fs.writeFileSync(bilibiliUserVideosFile, userVideosSource);
  }
}
