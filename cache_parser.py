import os
import sys
import gzip
import mimetypes
import pathlib
import hashlib
import brotli
import zlib
import struct
import datetime

# Add the cloned ccl_chromium_reader to sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CCL_PATH = os.path.join(SCRIPT_DIR, "ccl_chromium_reader")
if CCL_PATH not in sys.path:
    sys.path.insert(0, CCL_PATH)

from ccl_chromium_reader import ccl_chromium_cache

class CacheParser:
    def __init__(self, cache_dir: str):
        self.cache_dir = pathlib.Path(cache_dir)
        if not self.cache_dir.exists():
            raise FileNotFoundError(f"Cache directory not found: {cache_dir}")
            
        # Detect between Chrome and Firefox Cache2
        # Chrome Simple Cache has index-dir or data_0
        self.is_firefox = False
        self.cache_class = None
        
        # Firefox cache2 format check
        if (self.cache_dir / "entries").exists() or (self.cache_dir.parent.name == "cache2" and self.cache_dir.name == "entries") or any(f.name.isupper() and len(f.name) == 40 for f in self.cache_dir.iterdir() if f.is_file()):
            self.is_firefox = True
        else:
            self.cache_class = ccl_chromium_cache.guess_cache_class(self.cache_dir)
            if not self.cache_class:
                raise ValueError(f"Could not determine Chrome/Firefox cache type for {cache_dir}")

    def _parse_firefox_file(self, filepath: pathlib.Path) -> dict:
        try:
            with open(filepath, 'rb') as f:
                fileSize = filepath.stat().st_size
                if fileSize < 4: return None
                f.seek(-4, os.SEEK_END)
                metaStart = struct.unpack('>I', f.read(4))[0]
                
                chunkSize = 256 * 1024
                numHashChunks = metaStart // chunkSize
                if metaStart % chunkSize:
                    numHashChunks += 1
                
                offset = metaStart + 4 + numHashChunks * 2
                if offset >= fileSize: return None
                
                f.seek(offset)
                ver = struct.unpack('>I', f.read(4))[0]
                fetchCount = struct.unpack('>I', f.read(4))[0]
                lastFetchInt = struct.unpack('>I', f.read(4))[0]
                lastModInt = struct.unpack('>I', f.read(4))[0]
                frecency = struct.unpack('>I', f.read(4))[0]
                expireInt = struct.unpack('>I', f.read(4))[0]
                keySize = struct.unpack('>I', f.read(4))[0]
                if ver >= 2:
                    f.seek(4, os.SEEK_CUR)
                
                key = f.read(keySize)
                rest = f.read().split(b'\x00')
                headers = {}
                for i in range(1, len(rest)-1, 2):
                    if rest[i] and (i+1 < len(rest)):
                        try:
                            headers[rest[i].decode('ascii', errors='ignore').lower()] = rest[i+1].decode('utf-8', errors='ignore')
                        except:
                            pass
                            
                return {
                    'key': key.decode('utf-8', errors='ignore'),
                    'headers': headers,
                    'metaStart': metaStart,
                    'lastFetch': datetime.datetime.fromtimestamp(lastFetchInt).isoformat() if lastFetchInt else None,
                    'lastMod': datetime.datetime.fromtimestamp(lastModInt).isoformat() if lastModInt else None,
                }
        except Exception:
            return None

    def get_entries_metadata(self) -> list[dict]:
        if self.is_firefox:
            entries = []
            for file in self.cache_dir.iterdir():
                if not file.is_file() or file.name.lower() == 'index': continue
                parsed = self._parse_firefox_file(file)
                if not parsed: continue
                
                headers = parsed['headers']
                
                # Clean Firefox URL
                url = parsed['key']
                if "partitionKey=" in url:
                    idx = url.find(',:')
                    if idx != -1:
                        url = url[idx+2:]
                        
                content_type = "unknown"
                content_length = ""
                
                if 'response-head' in headers:
                    for line in headers['response-head'].split('\r\n'):
                        line_lower = line.lower()
                        if line_lower.startswith('content-type:'):
                            content_type = line.split(':', 1)[1].strip()
                        elif line_lower.startswith('content-length:'):
                            content_length = line.split(':', 1)[1].strip()
                
                entries.append({
                    "id": hashlib.md5(parsed['key'].encode()).hexdigest(),
                    "url": url,
                    "request_time": parsed['lastFetch'],
                    "response_time": parsed['lastMod'],
                    "content_type": content_type,
                    "content_length": content_length,
                    "mime": content_type.split(";")[0] if content_type else "unknown"
                })
            return entries
                
        # Chrome path
        entries = []
        with self.cache_class(self.cache_dir) as cache:
            for key in cache.keys():
                metas = cache.get_metadata(key)
                if not metas:
                    continue
                meta = metas[0]
                if meta:
                    content_type = (meta.get_attribute("content-type") or [""])[0]
                    content_length = (meta.get_attribute("content-length") or [""])[0]
                    
                    # Clean Chrome URL
                    url = key
                    if url.startswith("1/0/_dk_"):
                        tokens = url.split(" ")
                        for t in reversed(tokens):
                            if t.startswith("http"):
                                url = t
                                break
                                
                    entries.append({
                        "id": hashlib.md5(key.encode()).hexdigest(),
                        "url": url,
                        "request_time": meta.request_time.isoformat() if meta.request_time else None,
                        "response_time": meta.response_time.isoformat() if meta.response_time else None,
                        "content_type": content_type,
                        "content_length": content_length,
                        "mime": content_type.split(";")[0] if content_type else "unknown"
                    })
        return entries

    def get_entry_data(self, requested_id: str) -> dict:
        if self.is_firefox:
            for file in self.cache_dir.iterdir():
                if not file.is_file() or file.name.lower() == 'index': continue
                parsed = self._parse_firefox_file(file)
                if not parsed: continue
                
                if hashlib.md5(parsed['key'].encode()).hexdigest() == requested_id:
                    with open(file, 'rb') as f:
                        data = f.read(parsed['metaStart'])
                        
                    headers = parsed['headers']
                    content_type = "unknown"
                    content_encoding = ""
                    
                    if 'response-head' in headers:
                        for line in headers['response-head'].split('\r\n'):
                            line_lower = line.lower()
                            if line_lower.startswith('content-type:'):
                                content_type = line.split(':', 1)[1].strip()
                            elif line_lower.startswith('content-encoding:'):
                                content_encoding = line.split(':', 1)[1].strip()
                                
                    if content_encoding == "gzip":
                        try: data = gzip.decompress(data)
                        except: pass
                    elif content_encoding == "br":
                        try: data = brotli.decompress(data)
                        except: pass
                    elif content_encoding == "deflate":
                        try: data = zlib.decompress(data, -zlib.MAX_WBITS)
                        except: pass
                        
                    return {
                        "url": parsed['key'],
                        "content_type": content_type,
                        "payload": data
                    }
            return None
                
        # Chrome path
        with self.cache_class(self.cache_dir) as cache:
            for key in cache.keys():
                if hashlib.md5(key.encode()).hexdigest() == requested_id:
                    datas = cache.get_cachefile(key)
                    metas = cache.get_metadata(key)
                    
                    if not datas or not metas:
                        return None
                        
                    data = datas[0]
                    meta = metas[0]
                    
                    if not data or not meta:
                        return None
                        
                    content_encoding = (meta.get_attribute("content-encoding") or [""])[0]
                    content_type = (meta.get_attribute("content-type") or [""])[0]
                    
                    if content_encoding.strip() == "gzip":
                        try: data = gzip.decompress(data)
                        except: pass
                    elif content_encoding.strip() == "br":
                        try: data = brotli.decompress(data)
                        except: pass
                    elif content_encoding.strip() == "deflate":
                        try: data = zlib.decompress(data, -zlib.MAX_WBITS)
                        except: pass
                         
                    return {
                        "url": key,
                        "content_type": content_type,
                        "payload": data
                    }
        return None
