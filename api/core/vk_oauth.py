import httpx
from typing import Optional, Dict, Any
import secrets
import base64
import logging
from api.core.settings import VK_CLIENT_ID, VK_CLIENT_SECRET, VK_REDIRECT_URI, VK_API_VERSION
from api.core.schemas.auth import VKUserInfo  # Import from auth specifically

class VKOAuthService:
    def __init__(self):
        self.client_id = VK_CLIENT_ID
        self.client_secret = VK_CLIENT_SECRET
        self.redirect_uri = VK_REDIRECT_URI
        self.api_version = VK_API_VERSION
        self.base_url = "https://oauth.vk.com"
        self.api_url = "https://api.vk.com/method"
        # simple in-memory state storage; for production, replace with signed state or redis
        self._issued_states: set[str] = set()

    async def get_access_token(self, code: str) -> Optional[Dict[str, Any]]:
        """Exchange authorization code for access token"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/access_token",
                    params={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "redirect_uri": self.redirect_uri,
                        "code": code,
                    }
                )
                data = response.json()
                
                if "access_token" in data:
                    return data
                else:
                    logging.error(f"VK OAuth error: {data}")
                    return None
                    
        except Exception as e:
            logging.error(f"Error getting VK access token: {e}")
            return None

    async def get_user_info(self, access_token: str, user_id: int) -> Optional[VKUserInfo]:
        """Get user information from VK API"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_url}/users.get",
                    params={
                        "user_ids": user_id,
                        "fields": "photo_200,email",
                        "access_token": access_token,
                        "v": self.api_version,
                    }
                )
                data = response.json()
                
                if "response" in data and len(data["response"]) > 0:
                    user_data = data["response"][0]
                    return VKUserInfo(
                        id=user_data["id"],
                        first_name=user_data["first_name"],
                        last_name=user_data["last_name"],
                        email=user_data.get("email"),
                        photo_200=user_data.get("photo_200")
                    )
                else:
                    logging.error(f"VK API error: {data}")
                    return None
                    
        except Exception as e:
            logging.error(f"Error getting VK user info: {e}")
            return None

    def _generate_state(self) -> str:
        token = secrets.token_urlsafe(24)
        # keep compact
        state = base64.urlsafe_b64encode(token.encode()).decode().rstrip("=")
        self._issued_states.add(state)
        return state

    def validate_and_consume_state(self, state: Optional[str]) -> bool:
        if not state:
            return False
        if state in self._issued_states:
            self._issued_states.remove(state)
            return True
        return False

    def get_authorization_url(self) -> Dict[str, str]:
        """Generate VK OAuth authorization URL with state"""
        state = self._generate_state()
        url = (
            f"{self.base_url}/authorize?"
            f"client_id={self.client_id}&"
            f"redirect_uri={self.redirect_uri}&"
            f"response_type=code&"
            f"scope=email&"
            f"v={self.api_version}&"
            f"state={state}"
        )
        return {"url": url, "state": state}


# Create global instance
vk_oauth_service = VKOAuthService()