# -*- coding: utf-8 -*-
"""
飞书多维表格上传模块（基于 AutoVideo 技能 feishu_api.py 适配）

功能：
- 获取飞书表格记录
- 上传视频/图片到飞书
- 新增/更新多维表格记录
"""

import os
import time
import requests
from pathlib import Path
from typing import Dict, List, Optional, Any

# 飞书应用配置（与 AutoVideo 技能共用同一应用）
FEISHU_APP_ID = "cli_a934afe98ff51bc0"
FEISHU_APP_SECRET = "qpYYX8DDlScwsnCLeVMwnb7KhCLaPUb2"
FEISHU_BASE_URL = "https://open.feishu.cn/open-apis"

# 多维表格配置
APP_TOKEN = "U4tPbm14ia26UVsXhn3cryOjnYe"
TABLE_ID = "tbl5fI5MWC6YNWTs"  # Sheet1 表


class FeishuUploader:
    """飞书多维表格上传器"""

    def __init__(self, app_id: Optional[str] = None, app_secret: Optional[str] = None,
                 app_token: Optional[str] = None, table_id: Optional[str] = None):
        self.app_id = app_id or FEISHU_APP_ID
        self.app_secret = app_secret or FEISHU_APP_SECRET
        self.app_token = app_token or APP_TOKEN
        self.table_id = table_id or TABLE_ID
        self.access_token = None
        self.token_expires_at = 0

    def _get_access_token(self) -> str:
        """获取 tenant_access_token"""
        if self.access_token and time.time() < self.token_expires_at:
            return self.access_token

        url = f"{FEISHU_BASE_URL}/auth/v3/tenant_access_token/internal"
        headers = {"Content-Type": "application/json"}
        data = {"app_id": self.app_id, "app_secret": self.app_secret}

        response = requests.post(url, headers=headers, json=data, timeout=30)
        result = response.json()

        if result.get("code") == 0:
            self.access_token = result["tenant_access_token"]
            self.token_expires_at = time.time() + result.get("expire", 7200) - 300
            return self.access_token
        else:
            raise Exception(f"获取 access_token 失败: {result}")

    def _request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """发送 API 请求"""
        token = self._get_access_token()
        headers = kwargs.get("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        kwargs["headers"] = headers

        response = requests.request(method, url, **kwargs)
        result = response.json()

        if result.get("code") != 0:
            raise Exception(f"API 请求失败: {result.get('msg')}, code: {result.get('code')}")

        return result.get("data", {})

    def get_records(self, page_size: int = 100) -> List[Dict[str, Any]]:
        """获取所有记录"""
        url = f"{FEISHU_BASE_URL}/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records"

        all_records = []
        page_token = None

        while True:
            params = {"page_size": page_size}
            if page_token:
                params["page_token"] = page_token

            data = self._request("GET", url, params=params)
            items = data.get("items", [])
            all_records.extend(items)

            page_token = data.get("page_token")
            if not page_token or len(items) < page_size:
                break

        return all_records

    def get_max_index(self) -> int:
        """获取当前表格中最大的序号值"""
        records = self.get_records()
        max_index = 0
        for record in records:
            fields = record.get("fields", {})
            xuhao = fields.get("序号")
            if xuhao is not None:
                try:
                    max_index = max(max_index, int(xuhao))
                except (ValueError, TypeError):
                    pass
        return max_index

    def upload_file(self, file_path: str, file_type: str = "video") -> Dict[str, Any]:
        """上传文件到飞书"""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        url = f"{FEISHU_BASE_URL}/drive/v1/medias/upload_all"

        mime_types = {
            "video": "video/mp4",
            "image": "image/png",
            "file": "application/octet-stream"
        }
        mime_type = mime_types.get(file_type, "application/octet-stream")
        file_size = file_path.stat().st_size

        with open(file_path, "rb") as f:
            files = {
                "file": (file_path.name, f, mime_type),
                "file_name": (None, file_path.name),
                "parent_type": (None, "bitable_file"),
                "parent_node": (None, self.app_token),
                "size": (None, str(file_size))
            }
            headers = {"Authorization": f"Bearer {self._get_access_token()}"}
            response = requests.post(url, headers=headers, files=files, timeout=300)
            result = response.json()

        if result.get("code") == 0:
            return {
                "file_token": result["data"]["file_token"],
                "name": file_path.name,
                "size": file_size
            }
        else:
            raise Exception(f"文件上传失败: {result.get('msg')}")

    def create_record(self, fields: Dict[str, Any]) -> Dict[str, Any]:
        """新增一条记录"""
        url = f"{FEISHU_BASE_URL}/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records"
        data = self._request("POST", url, json={"fields": fields})
        return data.get("record", {})

    def update_record(self, record_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        """更新记录字段"""
        url = f"{FEISHU_BASE_URL}/bitable/v1/apps/{self.app_token}/tables/{self.table_id}/records/{record_id}"
        data = self._request("PUT", url, json={"fields": fields})
        return data.get("record", {})

    def upload_video_result(self, copywriting: str, video_path: str,
                            cover_path: Optional[str] = None,
                            summary: Optional[str] = None,
                            title: Optional[str] = None,
                            target_index: Optional[int] = None) -> Dict[str, Any]:
        """
        上传视频生成结果到飞书表格

        Args:
            copywriting: 视频文案
            video_path: 视频文件路径
            cover_path: 封面图片路径（可选）
            summary: 视频摘要（可选）
            title: 视频标题（可选，会作为摘要前缀）
            target_index: 指定序号（可选，默认自动递增）

        Returns:
            包含 record_id、更新字段的字典
        """
        # 上传视频
        video_info = self.upload_file(video_path, file_type="video")

        # 构建字段
        fields = {
            "人工优化版文案": copywriting,
            "视频": [{"file_token": video_info["file_token"], "name": video_info["name"], "size": video_info["size"]}]
        }

        if target_index is not None:
            fields["序号"] = target_index
        else:
            fields["序号"] = self.get_max_index() + 1

        if cover_path and Path(cover_path).exists():
            cover_info = self.upload_file(cover_path, file_type="image")
            fields["封面图片"] = [{"file_token": cover_info["file_token"], "name": cover_info["name"], "size": cover_info["size"]}]

        if summary:
            final_summary = summary
            if title:
                final_summary = f"{title}\n\n{summary}"
            fields["视频摘要"] = final_summary
        elif title:
            fields["视频摘要"] = title

        record = self.create_record(fields)
        return {
            "record_id": record.get("record_id"),
            "fields": fields
        }
