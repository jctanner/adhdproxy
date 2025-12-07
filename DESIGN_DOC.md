# ADHD Proxy Design Document

## Project Overview

ADHD Proxy is a filtering web proxy designed to reduce online distractions, particularly on YouTube and other content-heavy websites. The proxy provides a minimalist interface that allows users to consume content (especially music) without exposure to clickbait, intrusive advertisements, and potentially NSFW content.

### Goals

- Provide distraction-free access to YouTube music and videos
- Eliminate visual clutter and clickbait from web browsing
- Cache content locally to reduce repeated exposure to recommendation algorithms
- Offer a simple, text-focused interface for content discovery and playback
- Support multiple websites through a generic proxying mechanism

## Architecture

### Technology Stack

- **Framework**: Flask (Python web framework)
- **HTTP Client**: requests with requests_cache
- **HTML Parsing**: BeautifulSoup4
- **YouTube Integration**: yt-dlp
- **Logging**: logzero
- **Deployment**: Docker + Docker Compose

### High-Level Design

```
User Browser
    ↓
Flask App (Port 5002)
    ↓
┌─────────────────────────────────┐
│  URL Rewriting Engine           │
│  (replace_urls function)        │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│  Proxy Request Handler          │
│  - Web Request Cache            │
│  - Session Management           │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│  YouTube Special Handler        │
│  - Search Integration           │
│  - Video Metadata Cache         │
│  - Video File Cache             │
│  - Format Selection             │
└─────────────────────────────────┘
    ↓
External Websites / YouTube
```

## Core Components

### 1. Main Application (`flaskapp.py`)

The Flask application serves as the central routing and processing engine with three main route handlers:

- **`/` (index)**: Landing page with links to common sites
- **`/<path:path>`**: Generic proxy handler for any website
- **`/youtube`**: Specialized YouTube interface
- **`/files/youtube/<path:path>`**: Static file server for cached YouTube content

### 2. URL Rewriting Engine

The `replace_urls()` function is the core mechanism that makes proxying work:

**Purpose**: Transform all URLs in fetched HTML to route through the proxy

**Transformation Rules**:
- `https://example.com/path` → `/https.example.com/path`
- `http://example.com/path` → `/http.example.com/path`
- `/relative/path` → `/domain.com/relative/path`
- `//protocol-relative` → `/protocol-relative`

**Implementation Details** (flaskapp.py:31-78):
1. Parse HTML with BeautifulSoup
2. Extract all `href` and `src` attributes
3. Apply transformation rules based on URL format
4. Perform string replacement in the original HTML
5. Return modified HTML with all links proxied

### 3. Generic Proxy Handler

The `do_link()` function handles arbitrary website requests (flaskapp.py:81-119):

**Process**:
1. Parse incoming proxy-encoded URL
2. Extract protocol and domain information
3. Make HTTP request with custom headers
4. Apply URL rewriting to response
5. Return transformed HTML

**Features**:
- Request caching via `requests_cache` (15-minute cache at `/tmp/r.cache`)
- SSL verification disabled (for broader compatibility)
- Generic user agent to avoid bot detection

### 4. YouTube Integration

The proxy provides special handling for YouTube with three key capabilities:

#### Search Functionality
- Uses `yt-dlp` to search YouTube via command: `ytsearch5:{query}`
- Displays results as simple text links
- Caches search results metadata locally

#### Video Metadata Management
- Fetches complete video metadata using `yt-dlp -J {video_id}`
- Stores metadata in `youtube_cache/{video_id}/data.json`
- Metadata includes all available formats, codecs, and quality options

#### Video Download and Playback
- Downloads specific video/audio formats on-demand
- Naming pattern: `{video_id}_{format_id}.{extension}`
- Supports format selection via query parameters:
  - `?video={id}` - View video page with format options
  - `?video={id}&format={format_id}` - Download specific format
  - `?audio_only=1` - Audio-only mode (parameter parsed but not fully implemented)
  - `?video_only=1` - Video-only mode (parameter parsed but not fully implemented)

#### YouTube Templates

**`youtube.html`**:
- Search form
- List of videos (from search results or cached)
- Each video links to video detail page

**`youtube-video.html`**:
- Video title
- HTML5 video player (when format is selected)
- Table of all available formats with metadata
- "watch" and "listen" links for each format

## Key Features

### Distraction Reduction

1. **No Recommendations**: Content is accessed through search or direct links only
2. **Minimal UI**: Plain HTML with no CSS, JavaScript, or visual flourishes
3. **No Comments**: Only video content and metadata are displayed
4. **No Related Videos**: No algorithmic suggestions or sidebar content
5. **Text-Only Links**: No thumbnails or preview images

### Caching Strategy

The proxy implements two-tier caching:

**HTTP Request Cache**:
- Location: `/tmp/r.cache`
- Duration: Default (requests_cache default)
- Purpose: Avoid repeated fetches of the same web pages

**YouTube Content Cache**:
- Location: `youtube_cache/` (relative to app directory)
- Structure:
  ```
  youtube_cache/
  ├── {video_id_1}/
  │   ├── data.json
  │   ├── {video_id}_251.webm
  │   └── {video_id}_22.mp4
  ├── {video_id_2}/
  │   └── data.json
  ```
- Persistence: Permanent until manually deleted
- Purpose: Enable offline access and eliminate repeated downloads

### Multi-Site Support

While optimized for YouTube, the proxy can handle any website:

**Supported Sites** (via index.html):
- Hacker News (news.ycombinator.com)
- Reddit (reddit.com)
- Any arbitrary URL via manual entry

## Technical Implementation Details

### Route: `/<path:path>` (flaskapp.py:226-251)

This catch-all route handles all non-YouTube traffic:

1. Reconstructs full path including query strings
2. Special handling for YouTube watch URLs (delegates to prefetch, though `prefetch_youtube_video()` is undefined in current code)
3. Falls back to generic `do_link()` for other URLs

### Route: `/youtube` (flaskapp.py:128-222)

Complex handler with multiple code paths:

**Search Path** (`?q=query`):
- Execute yt-dlp search command
- Parse JSON output line-by-line
- Cache metadata for each result
- Display results list

**Video Detail Path** (`?video=id`):
- Load or fetch video metadata
- Parse available formats
- Display format selection table

**Format Download Path** (`?video=id&format=format_id`):
- Identify requested format from metadata
- Determine file extension based on codec
- Download video if not cached
- Render video player with cached file

### Session Management

Uses `requests.Session()` for HTTP connection pooling and cookie persistence across requests to the same domain.

## Deployment

### Docker Configuration

**Dockerfile**: Creates container with Python and dependencies

**docker-compose.yaml**:
- Service name: `adhdproxy`
- Port mapping: `5002:5002`
- Volume mount: `.:/app` (for live code editing)
- Command: `python flaskapp.py`

### Local Development

```bash
python flaskapp.py
```

Application runs on `http://0.0.0.0:5002` with Flask debug mode enabled.

## Security Considerations

### Known Security Issues

1. **SSL Verification Disabled**: `verify=False` in requests (flaskapp.py:115)
   - Reason: Broader compatibility with various sites
   - Risk: Vulnerable to MITM attacks
   - Mitigation: Intended for local/personal use only

2. **Command Injection Risk**: Shell commands constructed with f-strings (flaskapp.py:148, 186)
   - Risk: If video IDs or queries contain shell metacharacters
   - Mitigation: yt-dlp handles video IDs safely, queries are from trusted user
   - Recommendation: Use `subprocess.run()` with list arguments instead of `shell=True`

3. **No Authentication**: Open access to proxy
   - Risk: Anyone with network access can use the proxy
   - Mitigation: Intended for local deployment only

### Privacy Benefits

- No tracking cookies forwarded to destination sites
- Custom user agent prevents browser fingerprinting
- Local caching reduces data shared with YouTube
- No JavaScript execution means no client-side tracking

## Known Limitations

1. **Incomplete Implementation**: `prefetch_youtube_video()` function is referenced but not defined (flaskapp.py:246)

2. **Audio/Video Only Modes**: Parameters are parsed but not functionally implemented (flaskapp.py:138-139)

3. **No HTTPS Support**: Proxy itself runs on HTTP only

4. **Single User**: No concurrent request handling optimization

5. **No Resource Cleanup**: YouTube cache grows indefinitely

6. **Limited Error Handling**: Subprocess errors may crash routes

7. **No Content Filtering**: Beyond URL structure, no actual content analysis for NSFW/distraction filtering

## Future Enhancement Opportunities

### High Priority

1. **Implement Missing Functions**: Complete `prefetch_youtube_video()`
2. **Fix Command Injection**: Use argument lists instead of shell strings
3. **Audio-Only Support**: Actually use `audio_only` parameter to filter formats
4. **Error Handling**: Wrap subprocess calls in try/except blocks

### Medium Priority

1. **Cache Management**: Implement cache size limits and LRU eviction
2. **Playlist Support**: Handle YouTube playlists
3. **Thumbnail Blocking**: Strip image elements from proxied pages
4. **Configuration File**: Externalize cache paths, port, blocked domains
5. **HTTPS Support**: Add SSL certificates for encrypted proxy connection

### Low Priority

1. **Content Filtering**: Implement keyword-based content filtering
2. **Whitelist/Blacklist**: Domain-level access controls
3. **Statistics**: Track time spent, sites visited, videos watched
4. **Export Functionality**: Export cache inventory
5. **Multiple Profiles**: Different filtering settings per user/context

## Success Metrics

The proxy succeeds if it:

1. Allows music listening on YouTube without visual distractions
2. Prevents accidental navigation to recommended content
3. Reduces time spent browsing compared to native sites
4. Provides fast access to cached content
5. Remains simple to use and maintain

## Conclusion

ADHD Proxy achieves its core goal of reducing distractions through radical simplification: stripping websites down to HTML links and text, caching content locally, and providing a specialized interface for YouTube that bypasses the recommendation engine entirely. While the implementation has rough edges, the design philosophy is sound for users seeking a less addictive web browsing experience.
