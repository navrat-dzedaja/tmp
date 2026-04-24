// ==UserScript==
// @name         YouTube Music → NAS Downloader
// @namespace    https://github.com/navrat-dzedaja/tmp
// @version      0.1.0
// @description  When you watch a music video on YouTube, ping your NAS to archive the audio.
// @match        https://www.youtube.com/*
// @match        https://music.youtube.com/*
// @grant        GM_xmlhttpRequest
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_registerMenuCommand
// @grant        GM_notification
// @connect      *
// @run-at       document-idle
// ==/UserScript==

(function () {
    'use strict';

    // ---- Config (edit via Tampermonkey menu) -------------------------------
    const DEFAULTS = {
        // Where your NAS download server is listening. Example: http://nas.local:8787/download
        serverUrl: 'http://nas.local:8787/download',
        // Shared secret sent in the X-Api-Key header. Must match the server.
        apiKey: 'change-me',
        // Only send videos whose category is "Music". If false, send every watch page.
        musicOnly: true,
        // Require the video to actually start playing before sending (prevents spam from previews).
        requirePlayback: true,
        // Minimum seconds of playback before sending.
        minPlaybackSeconds: 5,
    };

    const cfg = new Proxy({}, {
        get: (_, k) => GM_getValue(k, DEFAULTS[k]),
        set: (_, k, v) => { GM_setValue(k, v); return true; },
    });

    function prompt_(label, current) {
        const v = window.prompt(label, current ?? '');
        return v === null ? undefined : v;
    }
    GM_registerMenuCommand('Set NAS server URL', () => {
        const v = prompt_('Server URL (POST endpoint):', cfg.serverUrl);
        if (v !== undefined) cfg.serverUrl = v.trim();
    });
    GM_registerMenuCommand('Set API key', () => {
        const v = prompt_('API key:', cfg.apiKey);
        if (v !== undefined) cfg.apiKey = v.trim();
    });
    GM_registerMenuCommand('Toggle music-only filter', () => {
        cfg.musicOnly = !cfg.musicOnly;
        GM_notification({ text: `musicOnly = ${cfg.musicOnly}`, timeout: 2000 });
    });
    GM_registerMenuCommand('Clear sent-video history', () => {
        GM_setValue('sentIds', '[]');
        GM_notification({ text: 'History cleared', timeout: 2000 });
    });

    // ---- De-dup cache ------------------------------------------------------
    const MAX_HISTORY = 500;
    function wasSent(id) {
        try { return JSON.parse(GM_getValue('sentIds', '[]')).includes(id); }
        catch { return false; }
    }
    function markSent(id) {
        let arr = [];
        try { arr = JSON.parse(GM_getValue('sentIds', '[]')); } catch {}
        if (!arr.includes(id)) arr.push(id);
        if (arr.length > MAX_HISTORY) arr = arr.slice(-MAX_HISTORY);
        GM_setValue('sentIds', JSON.stringify(arr));
    }

    // ---- Page introspection ------------------------------------------------
    function getVideoId() {
        const u = new URL(location.href);
        if (u.pathname === '/watch') return u.searchParams.get('v');
        // music.youtube.com also uses /watch?v=
        return null;
    }

    function getPlayerResponse() {
        // YouTube exposes the currently-loaded video metadata here.
        return window.ytInitialPlayerResponse
            || (window.ytplayer && window.ytplayer.config && window.ytplayer.config.args
                && safeParse(window.ytplayer.config.args.player_response));
    }
    function safeParse(s) { try { return JSON.parse(s); } catch { return null; } }

    function isMusic(pr) {
        if (!pr) return false;
        const cat = pr.microformat
            && pr.microformat.playerMicroformatRenderer
            && pr.microformat.playerMicroformatRenderer.category;
        if (cat === 'Music') return true;
        // music.youtube.com never exposes a category, but every video there is music.
        if (location.hostname === 'music.youtube.com') return true;
        return false;
    }

    function getTitle(pr) {
        return (pr && pr.videoDetails && pr.videoDetails.title) || document.title;
    }
    function getAuthor(pr) {
        return (pr && pr.videoDetails && pr.videoDetails.author) || '';
    }
    function getDuration(pr) {
        const s = pr && pr.videoDetails && pr.videoDetails.lengthSeconds;
        return s ? Number(s) : null;
    }

    // ---- Sending -----------------------------------------------------------
    function send(payload) {
        return new Promise((resolve, reject) => {
            GM_xmlhttpRequest({
                method: 'POST',
                url: cfg.serverUrl,
                headers: {
                    'Content-Type': 'application/json',
                    'X-Api-Key': cfg.apiKey,
                },
                data: JSON.stringify(payload),
                timeout: 15000,
                onload: r => (r.status >= 200 && r.status < 300) ? resolve(r) : reject(r),
                onerror: reject,
                ontimeout: reject,
            });
        });
    }

    async function handleVideo(videoId) {
        if (!videoId || wasSent(videoId)) return;

        const pr = getPlayerResponse();
        if (cfg.musicOnly && !isMusic(pr)) return;

        const payload = {
            videoId,
            url: `https://www.youtube.com/watch?v=${videoId}`,
            title: getTitle(pr),
            author: getAuthor(pr),
            durationSeconds: getDuration(pr),
            source: location.hostname,
        };

        markSent(videoId); // mark before send so rapid re-fires don't double up
        try {
            await send(payload);
            console.log('[yt-music-dl] queued', payload.title);
            GM_notification({
                title: 'Queued on NAS',
                text: payload.title,
                timeout: 3000,
            });
        } catch (e) {
            console.warn('[yt-music-dl] send failed', e);
            // Unmark so a later retry (e.g. next play) can succeed.
            const arr = JSON.parse(GM_getValue('sentIds', '[]')).filter(x => x !== videoId);
            GM_setValue('sentIds', JSON.stringify(arr));
        }
    }

    // ---- Playback tracking -------------------------------------------------
    // Only fire once the user has actually listened to the video for a bit.
    let watchTimer = null;
    let watchedId = null;

    function armForCurrentVideo() {
        const id = getVideoId();
        if (!id) return;
        if (id === watchedId) return; // already watching this one
        watchedId = id;
        clearTimeout(watchTimer);

        if (!cfg.requirePlayback) {
            handleVideo(id);
            return;
        }

        const video = document.querySelector('video');
        if (!video) {
            // Retry shortly; YT SPA can load the player after navigation.
            setTimeout(armForCurrentVideo, 500);
            return;
        }

        let accumulated = 0;
        let lastTs = null;
        const tick = () => {
            if (!video.paused && !video.ended) {
                const now = performance.now();
                if (lastTs !== null) accumulated += (now - lastTs) / 1000;
                lastTs = now;
            } else {
                lastTs = null;
            }
            if (accumulated >= cfg.minPlaybackSeconds) {
                clearInterval(watchTimer);
                handleVideo(id);
            }
        };
        watchTimer = setInterval(tick, 500);
    }

    // YouTube is a SPA — react to client-side navigation.
    window.addEventListener('yt-navigate-finish', armForCurrentVideo);
    window.addEventListener('yt-page-data-updated', armForCurrentVideo);
    document.addEventListener('DOMContentLoaded', armForCurrentVideo);
    armForCurrentVideo();
})();
