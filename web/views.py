# BOJ-tier
# Copyright (C) 2017  Jeehak Yoon, 2018 박수찬
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


from flask import Blueprint, request, render_template, session, redirect, url_for
from .extensions import redis_store, rq
from .utils import get_user_data, get_user_tier, ConvTier, ConvDiff, is_problem_rated
from .utils import get_problem_diffs, set_problem_diffs
import ujson
import time
import requests
from datetime import timedelta, datetime
import humanize
import os



front = Blueprint('', __name__, template_folder='templates', static_folder='static')


def render_template_with_user(f, **a):
    return render_template(f, me=session.get('id', ''), **a).replace("\n", "")


@front.route('/')
def index():
    return render_template_with_user('index.html')


@front.route('/tool/')
def tools():
    t = request.args.get('t', '')
    if t == 'prob':
        return render_template_with_user('tool_prob.html')
    return render_template_with_user('tool.html')


def GetRanking(handle):
    return redis_store.zcount("bojtier:user-ranking", get_user_tier(handle), 1e9)


@front.route("/user/<handle>/")
def user(handle):
    humanize.i18n.activate('ko_KR')

    data = get_user_data(handle)
    if data is None:
        return render_template_with_user("error.html")

    logged_in_user_handle = session.get("id", None)
    logged_in_user_data = get_user_data(logged_in_user_handle) if logged_in_user_handle is not None else None
    if logged_in_user_data is None:
        logged_in_user_data = {'solved_problem_ids': [], 'num_correct': 0, 'handle': '', 'time': 0, 'rank': 987654321}

    last_time = redis_store.get("bojtier:recent-time:{}".format(handle.lower())) or "0"
    if time.time() - float(last_time) > 300:
        observe_status.queue(handle, queue='high')
        redis_store.set("bojtier:recent-time:{}".format(handle.lower()), time.time())

    t = (datetime.utcnow() + timedelta(hours=9)).timestamp()
    cd = [(int(key.decode('utf-8')), val) for key, val in redis_store.zrevrange("bojtier:recent:{}".format(handle.lower()), 0, 20, withscores=True)]
    r = list((_[0], humanize.naturaltime(timedelta(seconds=t - _[1])),
              '' if logged_in_user_handle is None or _[0] not in logged_in_user_data['solved_problem_ids'] else ' class="correct"',
              ConvDiff(get_problem_diffs(_[0]))) for _ in cd)
    t = ConvTier(get_user_tier(handle))
    o = GetRanking(handle)

    redis_store.zrevrange("bojtier:recent:{}".format(handle.lower()), 0, 20, withscores=True)

    return render_template_with_user("user.html",
                                     u=handle,
                                     t=t,
                                     r=r,
                                     o=o)


@front.route("/login/", methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        session['id'] = request.form.get('id', '').strip()
        return redirect(url_for(".index"))
    return render_template_with_user("login.html")


def _recommend(data, diff):
    NUM_RECOMMENDS = 20

    len_order = redis_store.zcard("bojtier:problem-diffs")
    j = redis_store.zcount("bojtier:problem-diffs", 0, diff)
    rec = []
    for num_scope in range(50, MAX_NUM_TASKS, 50):
        rec = [(int(key.decode('utf-8')), val)
                for key, val in redis_store.zrange("bojtier:problem-diffs", max(j - num_scope, 0), min(j + num_scope, len_order), withscores=True)
               if int(key.decode('utf-8')) not in data['solved_problem_ids']]
        if len(rec) >= NUM_RECOMMENDS:
            break
    rec.sort(key=lambda x: abs(x[1] - diff))
    return [(key, ConvDiff(val)) for key, val in rec[:NUM_RECOMMENDS]]


@front.route("/recommend/")
def recommend():
    handle = session.get('id', None)
    if handle is None:
        return redirect(url_for(".login"))

    data = get_user_data(handle)
    if data is None:
        return render_template_with_user("error.html")

    y = get_user_tier(handle)
    z = y / 100
    ay = z * 4 / 5
    by = z
    cy = z * 5 / 4
    dy = 0
    a, b, c, d = (_recommend(data, _) for _ in (ay, by, cy, dy))
    return render_template_with_user('recommend.html',
                                     u=handle, t=ConvTier(y),
                                     ay=ConvDiff(ay), a=a,
                                     by=ConvDiff(by), b=b,
                                     cy=ConvDiff(cy), c=c,
                                     dy=dy, d=d)


@front.route("/ranking/<int:p>/")
def ranking(p):
    try:
        p = int(p) * 100
    except:
        p = 0
    t = redis_store.zrevrange("bojtier:user-ranking", p, p + 99, withscores=True)
    return render_template_with_user("ranking.html", t=[(p+i+1, v[0].decode('utf-8'), ConvTier(v[1])) for i, v in enumerate(t)])


@front.route("/problems/")
def problems():
    handle = session.get('id', '')
    if handle:
        data = get_user_data(handle)
        s = set(data.get('solved_problem_ids', []))
    else:
        s = set()
    x = list([i, 0, 0] for i in range(100))
    for r, q in redis_store.zrevrange("bojtier:problem-diffs", 0, MAX_NUM_TASKS, withscores=True):
        x[ConvDiff(q) // 100][1 if int(r.decode('utf-8')) in s else 2] += 1
    return render_template_with_user("problems.html", x=x)


@front.route("/problem/<int:p>/")
def problem(p):
    handle = session.get('id', '')
    if handle:
        data = get_user_data(handle)
        s = set(data.get('solved_problem_ids', []))
    else:
        s = set()

    if p < 0 or p > 99:
        p = 0

    t = redis_store.zrangebyscore("bojtier:problem-diffs", ConvDiff(p * 100, True), ConvDiff((p + 1) * 100, True), withscores=True)

    x = list()
    y = list()
    for r, q in t:
        r = int(r.decode('utf-8'))
        (y if r in s else x).append((r, ConvDiff(q)))

    return render_template_with_user("problem.html", x=x, y=y, p=p)


########
# Api


API_FAIL = ujson.dumps({ 'success': False, 'result': None })


def api_prob(data):
    if type(data) is not list:
        return None
    res = list()
    for prob in data:
        if type(prob) is not int:
            return None
        res.append({ 'diff': ConvDiff(get_problem_diffs(prob)) / 100, 'rated': is_problem_rated(prob) } if 0 <= prob < MAX_NUM_TASKS else { 'diff': 100.0, 'rated': False })
    return res


def api_user(data):
    if type(data) is not list:
        return None
    res = list()
    for u in data:
        if type(u) is not str:
            return None
        x = get_user_data(u)
        if x is None:
            res.append({ 'userid': None, 'tier': None, 'ranking': None })
            continue
        u = x['handle']
        res.append({ 'userid': u, 'tier': ConvTier(get_user_tier(u)) / 100, 'ranking': GetRanking(u) })
    return res


APIS = { 'prob': api_prob, 'user': api_user }


@front.route('/api/')
def api():
    return render_template_with_user('api.html')


@front.route('/api/<action>', methods = ['GET', 'POST'])
def api_action(action):
    if action not in APIS:
        return API_FAIL
    if request.is_json:
        data = request.get_json(silent = True)
    else:
        try:
            data = ujson.loads(request.values.get('q', ''))
        except ValueError:
            return API_FAIL
    func = APIS[action]
    res = func(data)
    return API_FAIL if res == None else ujson.dumps({ 'success': True, 'result': res})


MAX_NUM_TASKS = 20000


def update_user(handle):
    req = requests.get("https://acmicpc.net/user/{}".format(handle), timeout=30)
    if req.status_code == 200:
        data = {}
        content = req.content[req.content.index(b'<div class = "panel-body">'):]
        content = content[:content.index(b'</div>')]
        data['solved_problem_ids'] = list(set(int(int(chunk[:chunk.index(b'"')]))
                                              for chunk in content.split(b'<a href = "/problem/')[1::2]))
        del content

        data['num_correct'] = len(data['solved_problem_ids'])

        content = req.content[req.content.index('<th>랭킹</th>'.encode('utf-8')):]
        data['rank'] = int(content[content.index(b'<td>') + len('<td>'):content.index(b'</td>')])

        content = req.content[:req.content.index(b'</title>')]
        data['handle'] = content[content.index(b'<title>') + len(b'<title>'):].split()[0].decode('utf-8')

        data['time'] = time.time()

        redis_store.set("bojtier:user:{}".format(handle.lower()), ujson.dumps(data))
    elif req.status_code == 404:
        redis_store.delete("bojtier:user:{}".format(handle))


@rq.job(timeout=60*10)
def observe_ranking():
    page = redis_store.get('bojtier:current_ranking_page')
    page = int(page) if page is not None else 1

    req = requests.get("https://acmicpc.net/ranklist/{:d}".format(page))
    if req.status_code == 404:
        new_page = 1
    elif req.status_code == 200:
        new_page = page + 1
        for chunk in req.content.split(b'<a href="/user/')[1:]:
            handle = chunk[:chunk.index(b'"')]
            update_user(handle.decode('utf-8'))
    else:
        new_page = page

    redis_store.set('bojtier:current_ranking_page', new_page)


@rq.job(timeout=60*60*3)
def calculate_tier():
    temp_rankings = []
    temp_diffs = {}
    user_keys = redis_store.scan_iter('bojtier:user:*')
    for key in user_keys:
        handle = key[len("bojtier:user:"):]
        data = get_user_data(handle.decode('utf-8'))
        if data is None:
            continue
        x = [problem_id for problem_id in data['solved_problem_ids'] if is_problem_rated(problem_id)]
        z = sorted([get_problem_diffs(problem_id) for problem_id in x])
        r = 0
        for t in z:
            r = r * .99 + t
        temp_rankings.append((r, handle))
        if not r:
            continue
        r = 1 / r
        for problem_id in x:
            if problem_id not in temp_diffs:
                temp_diffs[problem_id] = r
            else:
                temp_diffs[problem_id] += r
    for r, handle in temp_rankings:
        redis_store.zadd("bojtier:user-ranking", r, handle)
    for problem_id, diff in temp_diffs.items():
        redis_store.zadd("bojtier:problem-diffs", 1 / diff ** .5, str(problem_id))


@rq.job(timeout=60*5)
def observe_problems():
    page = redis_store.get('bojtier:current_problem_page')
    page = int(page) if page is not None else 1
    req = requests.get("https://acmicpc.net/problemset/{:d}".format(page))
    if req.status_code == 404 or page * 100 > MAX_NUM_TASKS:
        new_page = 1
    elif req.status_code == 200:
        new_page = page + 1
        for chunk in req.content.split(b'<td class="click-this"><a href = "/problem/')[1:]:
            problem_id = int(chunk[:chunk.index(b'"')])
            is_rated = (b"label-warning" not in chunk[:400])
            redis_store.set("bojtier:problem-rated:{:d}".format(problem_id), ujson.dumps(is_rated))
    else:
        new_page = page
    redis_store.set('bojtier:current_problem_page', new_page)




@rq.job(timeout=60*10)
def observe_status(handle=None):
    T = time.time()
    r = requests.get('https://www.acmicpc.net/status/?result_id=4&user_id={}'.format(handle or ''), timeout = 5)
    if r.status_code == 200:
        r = r.content.split(b'<tr')
        for i in range(21, 1, -1):
            t = r[i]
            i = t.find(b'/user/')
            if i == -1:
                continue
            t = t[i + 6:]
            u = t[:t.index(b'"')].decode('utf-8')
            t = t[t.index(b'/problem/') + 9:]
            p = int(t[:t.index(b'"')])
            t = t[t.index(b'data-placement="top"  title="') + len(b'data-placement="top"  title="'):]
            d = [int("".join(chr(c) for c in chunk if chr(c).isdigit())) for chunk in t[:t.index(b'"')].split(b" ")]
            if handle is None:
                update_user(u)
            redis_store.zadd("bojtier:recent:{}".format(u.lower()),
                             datetime(year=d[0],month=d[1],day=d[2],hour=d[3],minute=d[4],second=d[5]).timestamp(),
                             p)
    if handle is not None:
        update_user(handle)


if "IS_SCHEDULER" in os.environ:
    observe_ranking.schedule(timedelta(minutes=5))
    observe_problems.schedule(timedelta(minutes=10))
    observe_status.schedule(timedelta(minutes=1), queue='high')
    calculate_tier.schedule(timedelta(minutes=10))