"""Localize public error details without changing status codes or the JSON schema."""
import re

from starlette.requests import Request


LOCALES = {"zh": "zh-CN", "en": "en-US", "ja": "ja-JP"}


def preferred_locale(request: Request) -> str:
    requested = request.query_params.get("lang")
    if requested is not None and requested in LOCALES.values():
        return requested
    for header in request.headers.get("accept-language", "").split(","):
        language = header.split(";", 1)[0].strip().lower().split("-", 1)[0]
        if language in LOCALES:
            return LOCALES[language]
    return "zh-CN"


_MESSAGES = {
    "请求次数过多，请稍后再试": (
        "Too many requests. Try again later.",
        "リクエストが多すぎます。しばらくしてから再試行してください。",
    ),
    "资源不存在": (
        "Resource not found.",
        "リソースが見つかりません。",
    ),
    "管理员密码至少需要 8 位": (
        "The administrator password must be at least 8 characters long.",
        "管理者パスワードは8文字以上で入力してください。",
    ),
    "系统已经初始化，请直接登录后台": (
        "Setup is already complete. Sign in to the admin console.",
        "初期設定は完了しています。管理画面にログインしてください。",
    ),
    "密码错误": (
        "Incorrect password.",
        "パスワードが正しくありません。",
    ),
    "未授权或授权校验失败": (
        "Your session is unauthorized. Sign in again.",
        "認証できませんでした。再度ログインしてください。",
    ),
    "文件状态无效": (
        "Invalid file status.",
        "ファイルのステータスが無効です。",
    ),
    "文件不存在": (
        "File not found.",
        "ファイルが見つかりません。",
    ),
    "登录有效期必须为 1 至 365 个整天": (
        "The session duration must be a whole number of days between 1 and 365.",
        "ログインの有効日数は1～365の整数で指定してください。",
    ),
    "上传已暂停，请稍后重试": (
        "Uploads are paused. Try again later.",
        "アップロードは一時停止中です。しばらくしてから再試行してください。",
    ),
    "设备凭证已改变，请刷新页面": (
        "The device credentials changed. Reload the page.",
        "デバイスの認証情報が変更されました。ページを再読み込みしてください。",
    ),
    "上传不存在": (
        "Upload not found.",
        "アップロードが見つかりません。",
    ),
    "上传已过期，请重新选择文件": (
        "The upload expired. Select the file again.",
        "アップロードの有効期限が切れました。ファイルを選び直してください。",
    ),
    "文件名无效": (
        "Invalid file name.",
        "ファイル名が無効です。",
    ),
    "全站容量不足，请等待到期清理": (
        "The site has reached its storage limit. Wait for expired files to be removed.",
        "サイトの容量上限に達しました。期限切れのファイルが削除されるまでお待ちください。",
    ),
    "磁盘可用空间不足": (
        "Insufficient free disk space.",
        "ディスクの空き容量が不足しています。",
    ),
    "上传状态不允许写入": (
        "This upload is not accepting data in its current state.",
        "現在のアップロード状態ではデータを書き込めません。",
    ),
    "分片索引无效": (
        "Invalid chunk index.",
        "チャンクのインデックスが無効です。",
    ),
    "缺少分片 SHA256": (
        "The chunk SHA-256 checksum is missing.",
        "チャンクの SHA-256 チェックサムがありません。",
    ),
    "分片长度超出声明": (
        "The chunk exceeds its declared length.",
        "チャンクのサイズが指定されたサイズを超えています。",
    ),
    "上传等待数据超时，请重试": (
        "The upload timed out while waiting for data. Try again.",
        "アップロードデータの受信待ちがタイムアウトしました。もう一度お試しください。",
    ),
    "分片长度或 SHA256 不匹配": (
        "The chunk length or SHA-256 checksum does not match.",
        "チャンクのサイズまたは SHA-256 チェックサムが一致しません。",
    ),
    "上传已取消": (
        "The upload was cancelled.",
        "アップロードはキャンセルされました。",
    ),
    "此会话需要分片上传": (
        "This session requires a chunked upload.",
        "このセッションでは分割アップロードが必要です。",
    ),
    "分片实体丢失，请重传": (
        "An uploaded chunk is missing. Upload the file again.",
        "アップロード済みのチャンクが見つかりません。もう一度アップロードしてください。",
    ),
    "分片实体损坏，请重传": (
        "An uploaded chunk is corrupted. Upload the file again.",
        "アップロード済みのチャンクが破損しています。もう一度アップロードしてください。",
    ),
    "文件总长度或完整 SHA256 不匹配，请重传": (
        "The file size or SHA-256 checksum does not match. Upload the file again.",
        "ファイルサイズまたは SHA-256 チェックサムが一致しません。もう一度アップロードしてください。",
    ),
    "上传已取消或过期": (
        "The upload was cancelled or has expired.",
        "アップロードはキャンセルされたか、有効期限が切れました。",
    ),
    "分片不完整": (
        "Some upload chunks are missing.",
        "アップロードのチャンクがそろっていません。",
    ),
    "上传状态已改变": (
        "The upload status has changed.",
        "アップロードの状態が変更されました。",
    ),
    "文件校验或发布失败，可重试上传": (
        "File verification or publishing failed. You can retry the upload.",
        "ファイルの検証または公開に失敗しました。アップロードを再試行できます。",
    ),
    "文件已发布，请从列表删除": (
        "The file has already been published. Delete it from the file list.",
        "ファイルはすでに公開されています。ファイル一覧から削除してください。",
    ),
    "文件不存在或已到期": (
        "The file was not found or has expired.",
        "ファイルが見つからないか、有効期限が切れています。",
    ),
    "文件实体不存在": (
        "The file is missing from storage.",
        "保存先にファイルが見つかりません。",
    ),
    "Range 不可用": (
        "The requested download range is unavailable.",
        "指定されたダウンロード範囲を取得できません。",
    ),
    "设备凭证已失效，请重新输入口令": (
        "The device credentials expired. Enter the pairing code again.",
        "デバイスの認証情報が無効です。ペアリングコードを入力し直してください。",
    ),
    "配对已在其他标签页改变，请刷新": (
        "The pairing changed in another tab. Reload the page.",
        "別のタブでペアリングが変更されました。ページを再読み込みしてください。",
    ),
    "设备不存在": (
        "Device not found.",
        "デバイスが見つかりません。",
    ),
    "请通过同源页面操作": (
        "Perform this action from the FileRelay page.",
        "FileRelay のページから操作してください。",
    ),
    "CSRF 校验失败，请刷新页面": (
        "The security check failed. Reload the page.",
        "セキュリティチェックに失敗しました。ページを再読み込みしてください。",
    ),
    "配对操作过于频繁，请稍后重试": (
        "Too many pairing attempts. Try again later.",
        "ペアリングの試行回数が多すぎます。しばらくしてから再試行してください。",
    ),
    "原设备状态已改变，请重新申请": (
        "The original device state changed. Submit a new request.",
        "元のデバイスの状態が変わりました。再度申請してください。",
    ),
    "口令必须是 1 至 4 位数字": (
        "The pairing code must contain 1 to 4 digits.",
        "ペアリングコードは1～4桁の数字で入力してください。",
    ),
    "申请不存在": (
        "Request not found.",
        "申請が見つかりません。",
    ),
    "旧公开接口已关闭，请使用 FileRelay 配对首页": (
        "The legacy public API is unavailable. Use the FileRelay pairing page.",
        "旧公開 API は利用できません。FileRelay のペアリング画面をご利用ください。",
    ),
    "系统未初始化，请先完成初始化": (
        "Complete setup before using FileRelay.",
        "FileRelay を使用する前に初期設定を完了してください。",
    ),
}

_PATTERNS = (
    (
        re.compile(r"单文件上限必须大于 0 且不能超过 ([\d.]+ [MG]B)"),
        "The single-file limit must be greater than 0 and no greater than {0}.",
        "1ファイルの上限は0より大きく、{0} 以下にしてください。",
    ),
    (
        re.compile(r"全站容量必须大于 0 且不能超过 ([\d.]+ [MG]B)"),
        "The site storage limit must be greater than 0 and no greater than {0}.",
        "サイト全体の容量上限は0より大きく、{0} 以下にしてください。",
    ),
    (
        re.compile(r"文件大小超过单文件上限（([\d.]+ [MG]B)）"),
        "The file exceeds the {0} limit.",
        "ファイルが上限の {0} を超えています。",
    ),
    (
        re.compile(r"(open_upload|show_admin_addr) 必须是 0 或 1"),
        "{0} must be 0 or 1.",
        "{0} は0または1で指定してください。",
    ),
    (
        re.compile(r"(admin_token) 格式或长度错误"),
        "{0} has an invalid format or length.",
        "{0} の形式または長さが無効です。",
    ),
    (
        re.compile(r"不支持的设置项：.*"),
        "One or more settings are unsupported.",
        "未対応の設定項目があります。",
    ),
    (
        re.compile(r"token验证失败: .*"),
        "The session expired or is invalid. Sign in again.",
        "セッションが無効か、有効期限が切れています。再度ログインしてください。",
    ),
)

_FALLBACKS = {
    400: ("The request could not be processed.", "リクエストを処理できませんでした。"),
    404: _MESSAGES["资源不存在"],
    422: ("One or more values are invalid.", "入力値の一部が無効です。"),
    500: ("An internal error occurred. Try again later.", "内部エラーが発生しました。しばらくしてから再試行してください。"),
}
_DEFAULT = ("The request failed. Try again later.", "リクエストに失敗しました。しばらくしてから再試行してください。")


def localize_error(detail: str, locale: str, status: int) -> str:
    if locale == "zh-CN":
        return detail

    index = 0 if locale == "en-US" else 1
    if detail in _MESSAGES:
        return _MESSAGES[detail][index]
    for pattern, english, japanese in _PATTERNS:
        if match := pattern.fullmatch(detail):
            return (english, japanese)[index].format(*match.groups())
    return _FALLBACKS.get(status, _DEFAULT)[index]
