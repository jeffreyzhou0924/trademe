"""
OKX API认证服务
提供OKX API调用的签名认证功能
"""

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime
from typing import Dict, Optional

import aiohttp


class OKXAuthService:
    """OKX API认证服务"""
    
    def __init__(self, api_key: str, secret_key: str, passphrase: str, sandbox: bool = False):
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase
        
        # API基础URL
        if sandbox:
            self.base_url = "https://www.okx.com"  # 沙盒环境
        else:
            self.base_url = "https://www.okx.com"  # 生产环境
        
        self.api_url = f"{self.base_url}/api/v5"
    
    def _generate_signature(self, timestamp: str, method: str, request_path: str, body: str = '') -> str:
        """生成OKX API签名"""
        # 构造签名字符串
        message = timestamp + method.upper() + request_path + body
        
        # 使用HMAC-SHA256生成签名
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        # Base64编码
        return base64.b64encode(signature).decode('utf-8')
    
    def _get_headers(self, method: str, request_path: str, body: str = '') -> Dict[str, str]:
        """生成请求头"""
        # OKX API要求使用毫秒时间戳或ISO格式
        timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        
        signature = self._generate_signature(timestamp, method, request_path, body)
        
        headers = {
            'Content-Type': 'application/json',
            'OK-ACCESS-KEY': self.api_key,
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': self.passphrase,
        }
        
        return headers
    
    async def authenticated_request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict] = None, 
        data: Optional[Dict] = None,
        timeout: int = 10
    ) -> Dict:
        """发起认证的API请求"""
        
        # 构造完整URL路径
        request_path = f"/api/v5{endpoint}"
        full_url = f"{self.api_url}{endpoint}"
        
        # 处理查询参数
        if params:
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            request_path += f"?{query_string}"
            full_url += f"?{query_string}"
        
        # 处理请求体
        body_str = ''
        if data and method.upper() in ['POST', 'PUT']:
            body_str = json.dumps(data)
        
        # 生成请求头
        headers = self._get_headers(method.upper(), request_path, body_str)
        
        # 发起请求
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method.upper(),
                full_url,
                headers=headers,
                json=data if data else None,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    raise Exception(f"OKX API错误 {response.status}: {error_text}")
    
    async def get_market_data(
        self, 
        instrument_id: str, 
        bar: str, 
        limit: int = 100,
        after: Optional[str] = None,
        before: Optional[str] = None
    ) -> Dict:
        """获取市场K线数据 - 使用认证API"""
        
        params = {
            "instId": instrument_id,
            "bar": bar,
            "limit": str(limit)
        }
        
        if after:
            params["after"] = after
        if before:
            params["before"] = before
        
        return await self.authenticated_request("GET", "/market/candles", params=params)
    
    async def test_connection(self) -> bool:
        """测试API连接和认证"""
        try:
            # 调用账户信息接口测试认证
            result = await self.authenticated_request("GET", "/account/account-position-risk")
            return result.get("code") == "0"
        except Exception as e:
            print(f"OKX API认证测试失败: {e}")
            return False


# 全局OKX认证服务实例
okx_auth_service: Optional[OKXAuthService] = None


def initialize_okx_auth(api_key: str, secret_key: str, passphrase: str, sandbox: bool = False):
    """初始化OKX认证服务"""
    global okx_auth_service
    okx_auth_service = OKXAuthService(api_key, secret_key, passphrase, sandbox)
    return okx_auth_service


def get_okx_auth_service() -> Optional[OKXAuthService]:
    """获取OKX认证服务实例"""
    return okx_auth_service