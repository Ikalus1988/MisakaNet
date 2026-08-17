def notify_feishu(payload):
    webhook = os.environ.get('FEISHU_WEBHOOK')
    if not webhook: return False
    req = urllib.request.Request(webhook, json.dumps({'msg_type': 'text', 'content': {'text': payload}}).encode('utf-8'))
    return urllib.request.urlopen(req, timeout=5).status == 200