# BOJ-tier
# Copyright (C) 2017  Jeehak Yoon
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

import requests
from .extensions import redis_store
import math
import ujson
import time


def ConvTier(x, f = False):
    if x is None: return 0
    return math.expm1(x / 194) / 5 if f else int(math.log1p(x * 5) * 194)


def ConvDiff(x, f = False):
    if x is None: return 0
    return math.expm1(x / 1608) / 5 if f else int(math.log1p(x * 5) * 1608)


def get_user_data(handle):
    data = redis_store.get("bojtier:user:{}".format(handle.lower()))
    return None if data is None else ujson.loads(data)


def get_user_tier(handle):
    return redis_store.zscore("bojtier:user-ranking", handle.lower())


def is_problem_rated(problem_id):
    data = redis_store.get("bojtier:problem-rated:{:d}".format(problem_id))
    if data is not None:
        is_rated, stored_time = ujson.loads(data)
        if time.time() - stored_time <= 24 * 60 * 14: # 14일에 한 번씩 물어봄
            return is_rated

    req = requests.get("https://acmicpc.net/problem/{:d}".format(problem_id), timeout=10)
    is_rated = False
    if req.status_code == 200:
        is_rated = (req.content.find(b'label-warning') == -1)
    redis_store.set("bojtier:problem-rated:{:d}".format(problem_id), ujson.dumps([is_rated, time.time()]))

    return is_rated


def get_problem_diffs(problem_id):
    return redis_store.zscore("bojtier:problem-diffs", str(problem_id)) or 100.26
