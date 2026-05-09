from __future__ import annotations


APP_PACKAGES: dict[str, str] = {
    "淘宝": "com.taobao.taobao",
    "淘宝闪购": "com.taobao.taobao",
    "京东": "com.jingdong.app.mall",
    "拼多多": "com.xunmeng.pinduoduo",
    "微信": "com.tencent.mm",
    "小红书": "com.xingin.xhs",
    "抖音": "com.ss.android.ugc.aweme",
    "美团": "com.sankuai.meituan",
    "盒马": "com.wudaokou.hippo",
    "设置": "com.android.settings",
}


def resolve_app_package(app_name: str) -> str | None:
    if app_name.startswith("com."):
        return app_name
    return APP_PACKAGES.get(app_name)
