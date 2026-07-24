# -*- coding: utf-8 -*-
"""夜班烘焙 hands/night_bake.py — 哑手: 采收→双层拼装→单次API→冻结→装药。
无判断,无重试策略,任何失败=落盘 ERROR 文件后退出。首跑联调走维修工单,不走操盘手。"""
import json, os, sys, glob, datetime, urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = datetime.date.today().strftime('%Y%m%d')
CFG = json.load(open(os.path.join(REPO, 'hands', 'config.json'), encoding='utf-8'))
# config.json: {"api_url":..., "api_key":..., "model":"glm-5.2", "review_cmd":...}  ←副驾装机时填

def die(stage, err):
    open(os.path.join(REPO, 'ammo', f'{TODAY}-ERROR.txt'), 'w', encoding='utf-8').write(f'{stage}\n{err}')
    sys.exit(1)

def step1_harvest():
    """采收: 调用现行复盘管线(hands/kernel.py),产出当日账本JSON路径。"""
    code = os.system(CFG['review_cmd'])                     # 既有管线,含首封/开板透传
    if code != 0: die('采收', f'review_cmd exit {code}')
    return os.path.join(REPO, 'ledger', 'archive', f'review_{TODAY}.json')

def step2_assemble(ledger_path):
    grammar = open(os.path.join(REPO, 'grammar', 'brief_v2.txt'), encoding='utf-8').read()
    cutoff = (datetime.date.today() - datetime.timedelta(days=30)).strftime('%Y%m%d')
    genes = []
    for f in sorted(glob.glob(os.path.join(REPO, 'genes', '对话记录', '*.md')), key=os.path.getmtime):
        if datetime.date.fromtimestamp(os.path.getmtime(f)).strftime('%Y%m%d') >= cutoff:
            genes.append(f'===== 基因: {os.path.basename(f)[:40]} (单#行=操盘手原话,权重最高) =====\n'
                         + open(f, encoding='utf-8', errors='replace').read())
    ledger = open(ledger_path, encoding='utf-8').read()
    task = ('你是夜读席。基于以上语法层与世界层,对账本内每票产出JSON: '
            '{"regime":{"word":"","why":""},"recall":[{"symbol":"","name":"","why":"",'
            '"trigger":["地标算术,如 prem > 2"],"invalid":["同"],"L0":""}],'
            '"scout_payload":["明日侦察猎杀问题×3-5,带假设"],"notes":""} 只输出JSON。'
            '剧本条件只许引用字段: open/prem/limit/amount。')
    return f'===== 语法层 =====\n{grammar}\n\n' + '\n\n'.join(genes) + f'\n\n===== 当日账本 =====\n{ledger}\n\n===== 任务 =====\n{task}'

def step3_night_read(prompt):
    req = urllib.request.Request(CFG['api_url'], method='POST',
        headers={'Content-Type': 'application/json', 'Authorization': f"Bearer {CFG['api_key']}"},
        data=json.dumps({'model': CFG['model'], 'messages': [{'role': 'user', 'content': prompt}],
                         'temperature': 0.2}).encode())
    try:
        resp = json.load(urllib.request.urlopen(req, timeout=1800))
        txt = resp['choices'][0]['message']['content']
        return json.loads(txt[txt.find('{'): txt.rfind('}') + 1])
    except Exception as e:
        die('夜读', repr(e))

def step4_freeze(out):
    # 冻结前唯一校验: 剧本条件是否纯地标算术(白名单token),不合规=整票剔除并记录,不修补
    allowed = set('open prem limit amount and or not < > = . ( ) 0123456789'.split() + [' '])
    plays, rejected = [], []
    for p in out.get('recall', []):
        ok = all(all(tok in {'open','prem','limit','amount','and','or','not'} or
                     all(c in '<>=.()0123456789- ' for c in tok)
                     for tok in cond.replace('(',' ( ').replace(')',' ) ').split())
                 for cond in p.get('trigger', []) + p.get('invalid', []))
        (plays if ok else rejected).append(p)
    frozen = {'auction_date': (datetime.date.today() + datetime.timedelta(days=1)).isoformat(),
              'regime': out.get('regime'), 'plays': plays, 'rejected_nonlandmark': rejected}
    json.dump(frozen, open(os.path.join(REPO, 'ammo', f'{TODAY}-剧本.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    # 弹药卡(给沙盘的中文视图)与侦察装药
    card = [f"# {TODAY} 弹药卡 | régime推定[{frozen['regime']['word']}]: {frozen['regime']['why']}", '']
    for p in plays:
        card += [f"### {p['name']} — {p['why']}", f"触发: {p['trigger']} | 失效: {p['invalid']} | 死线L0: {p['L0']}", '']
    open(os.path.join(REPO, 'ammo', f'{TODAY}-弹药卡.md'), 'w', encoding='utf-8').write('\n'.join(card))
    open(os.path.join(REPO, 'ammo', f'{TODAY}-侦察装药.md'), 'w', encoding='utf-8').write(
        f"# {TODAY} 明日侦察装药(贴入SCOUT第1发;否决改写权在操盘手)\n\n" +
        '\n'.join(f"- {q}" for q in out.get('scout_payload', [])))

if __name__ == '__main__':
    step4_freeze(step3_night_read(step2_assemble(step1_harvest())))
    print('frozen', TODAY)
