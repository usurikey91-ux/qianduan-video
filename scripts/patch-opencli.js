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
fs.writeFileSync(file, source);
console.log('Patched OpenCLI Douyin user-videos output');
