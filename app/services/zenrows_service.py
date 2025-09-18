"""
ZenRows service
"""
import requests
import asyncio
from typing import Dict, Any, Optional
from app.config import settings

class ZenRowsService:
    """Service to bypass Cloudflare protection using ZenRows"""
    
    def __init__(self):
        self.api_key = getattr(settings, 'zenrows_api_key', None)
        self.base_url = 'https://api.zenrows.com/v1/'
    
    async def fetch_manga_info(self, manga_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch manga info (hid, title)
        
        Args:
            manga_id: The manga ID from client
            
        Returns:
            Dict with manga info or None if failed
        """
        if not self.api_key:
            print("❌ ZenRows API key not configured")
            return None
        
        target_url = f'https://api.comick.fun/comic/{manga_id}/'
        
        try:
            print(f"🌐 Using ZenRows to fetch manga info: {target_url}")
            
            params = {
                'url': target_url,
                'apikey': self.api_key,
                'js_render': 'true',
                'premium_proxy': 'true',
            }
            
            response = requests.get(self.base_url, params=params, timeout=30)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    comic_data = data.get('comic', {})
                    
                    hid = comic_data.get('hid')
                    title = comic_data.get('title')
                    
                    if hid and title:
                        print(f"✅ ZenRows success! Got manga info for {manga_id}: {title} (hid: {hid})")
                        return {
                            'hid': hid,
                            'title': title,
                            'full_data': data
                        }
                    else:
                        print(f"❌ Missing hid or title in API response for {manga_id}")
                        return None
                except ValueError as e:
                    print(f"❌ ZenRows returned invalid JSON: {e}")
                    print(f"🔍 Response preview: {response.text[:200]}...")
                    return None
            else:
                print(f"❌ ZenRows error {response.status_code}: {response.text[:200]}...")
                return None
                
        except requests.exceptions.Timeout:
            print("❌ ZenRows request timed out")
            return None
        except requests.exceptions.RequestException as e:
            print(f"❌ ZenRows request failed: {e}")
            return None
        except Exception as e:
            print(f"❌ Unexpected ZenRows error: {e}")
            return None

    async def fetch_manga_chapters(self, manga_hid: str) -> Optional[Dict[str, Any]]:
        """
        Fetch manga chapters
        
        Args:
            manga_hid: The manga hid to fetch chapters for
            
        Returns:
            JSON response with chapters data or None if failed
        """
        if not self.api_key:
            print("❌ ZenRows API key not configured")
            return None
        
        target_url = f'https://api.comick.fun/comic/{manga_hid}/chapters?date-order=2&lang=en'
        
        try:
            print(f"🌐 Using ZenRows to fetch: {target_url}")
            
            params = {
                'url': target_url,
                'apikey': self.api_key,
                'js_render': 'true',
                'premium_proxy': 'true',
            }
            
            response = requests.get(self.base_url, params=params, timeout=30)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    chapters = data.get('chapters', [])
                    print(f"✅ ZenRows success! Fetched {len(chapters)} chapters for {manga_hid}")
                    return data
                except ValueError as e:
                    print(f"❌ ZenRows returned invalid JSON: {e}")
                    print(f"🔍 Response preview: {response.text[:200]}...")
                    return None
            else:
                print(f"❌ ZenRows error {response.status_code}: {response.text[:200]}...")
                return None
                
        except requests.exceptions.Timeout:
            print("❌ ZenRows request timed out")
            return None
        except requests.exceptions.RequestException as e:
            print(f"❌ ZenRows request failed: {e}")
            return None
        except Exception as e:
            print(f"❌ Unexpected ZenRows error: {e}")
            return None
    
    def test_connection(self) -> bool:
        """Test ZenRows connection with a simple request"""
        if not self.api_key:
            print("❌ ZenRows API key not configured")
            return False
        
        try:
            print("🧪 Testing ZenRows connection...")
            
            params = {
                'url': 'https://httpbin.org/ip',
                'apikey': self.api_key,
            }
            
            response = requests.get(self.base_url, params=params, timeout=10)
            
            if response.status_code == 200:
                print("✅ ZenRows connection test successful")
                return True
            else:
                print(f"❌ ZenRows connection test failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ ZenRows connection test error: {e}")
            return False

zenrows_service = ZenRowsService()