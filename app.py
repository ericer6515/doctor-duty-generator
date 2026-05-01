from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import date, datetime
from typing import Dict, List, Optional, Set, Tuple
import calendar
import json
from flask import Flask, jsonify, render_template, request

try:
    from taiwan_holidays.taiwan_calendar import TaiwanCalendar
    TW_HOLIDAY_AVAILABLE = True
except Exception:
    TaiwanCalendar = None
    TW_HOLIDAY_AVAILABLE = False

app = Flask(__name__)

@dataclass
class Doctor:
    id: str
    name: str
    target_shifts: Optional[int] = None

@dataclass
class Ward:
    id: str
    name: str

class DutyScheduler:
    def __init__(
        self,
        doctors: List[Doctor],
        wards: List[Ward],
        doctor_off: Dict[str, Set[str]],
        ward_off: Dict[str, Set[str]],
        manual_holidays: Dict[str, str],
        fixed_assignments: Dict[str, Dict[str, str]] | None = None,
        forbidden_pairs: List[Tuple[str, str]] | None = None,
    ):
        self.doctors = doctors
        self.wards = wards
        self.doctor_off = doctor_off
        self.ward_off = ward_off
        self.manual_holidays = manual_holidays
        self.fixed_assignments = fixed_assignments or {}
        self.forbidden_pairs = forbidden_pairs or []
        self.calendar = TaiwanCalendar() if TW_HOLIDAY_AVAILABLE else None

    def next_month(self, today: Optional[date] = None) -> Tuple[int, int]:
        today = today or date.today()
        if today.month == 12:
            return today.year + 1, 1
        return today.year, today.month + 1

    def holiday_name(self, d: date) -> Optional[str]:
        iso = d.isoformat()
        if iso in self.manual_holidays:
            return self.manual_holidays[iso]
        if self.calendar:
            try:
                if self.calendar.is_holiday(d):
                    return '台灣假日'
            except Exception:
                return None
        return None

    def month_meta(self, year: int, month: int):
        total = calendar.monthrange(year, month)[1]
        out = []
        for day in range(1, total + 1):
            d = date(year, month, day)
            out.append({
                'date': d.isoformat(),
                'day': day,
                'weekday': d.weekday(),
                'weekend': d.weekday() >= 5,
                'holiday_name': self.holiday_name(d),
            })
        return out

    def _violates_forbidden_pair(self, doctor_id: str, same_day_used: Set[str]) -> bool:
        """檢查若今天再排 doctor_id，是否會跟已排名單組成禁止同日的 pair。"""
        for a, b in self.forbidden_pairs:
            if doctor_id == a and b in same_day_used:
                return True
            if doctor_id == b and a in same_day_used:
                return True
        return False

    def _doctor_score(
        self,
        doctor: Doctor,
        day: int,
        doctor_days: Dict[str, List[int]],
        same_day_used: Set[str],
        current_count: Dict[str, int],
    ):
        """偏重目標班數且絕對不超標：分數越小越優先。"""
        # 同一天已經在別病房值班了 → 直接丟掉
        if doctor.id in same_day_used:
            return (10**9, 0, 0, 0, 0, doctor.name)

        prev_days = sorted(doctor_days.get(doctor.id, []))
        min_gap = 999 if not prev_days else min(abs(day - d) for d in prev_days)

        # 硬約束：禁止隔天連班（min_gap < 2）
        hard_penalty = 10**8 if min_gap < 2 else 0

        current = current_count.get(doctor.id, 0)
        # 若有設定目標班數，視為上限，絕對不能超過
        if doctor.target_shifts is not None and current >= doctor.target_shifts:
            return (10**9, 0, 0, 0, 0, doctor.name)

        target = doctor.target_shifts if doctor.target_shifts is not None else 10**6

        # 距離目標還差多少（越大越應該被排班）
        delta_to_target = target - current

        # 間隔懲罰：盡量保持 >=3 天，>=4 天最好
        if min_gap == 999:
            gap_penalty = 0
        elif min_gap >= 4:
            gap_penalty = 0
        elif min_gap >= 3:
            gap_penalty = 50
        else:  # min_gap == 2（<2 已由 hard_penalty 擋住）
            gap_penalty = 200

        # 排序 key：
        # 1) hard_penalty：硬違規在最後
        # 2) -delta_to_target：離目標越遠越優先
        # 3) gap_penalty：間隔越好越優先
        # 4) current：目前班數越少越優先
        return (
            hard_penalty,
            -delta_to_target,
            gap_penalty,
            current,
            doctor.name,
        )

    def generate(self, year: int, month: int):
        total = calendar.monthrange(year, month)[1]
        assignments: Dict[str, Dict[int, Optional[str]]] = {w.id: {d: None for d in range(1, total+1)} for w in self.wards}
        doctor_days: Dict[str, List[int]] = {d.id: [] for d in self.doctors}
        current_count: Dict[str, int] = {d.id: 0 for d in self.doctors}
        unfilled = []

        for day in range(1, total + 1):
            same_day_used: Set[str] = set()
            iso = date(year, month, day).isoformat()
            for ward in self.wards:
                if iso in self.ward_off.get(ward.id, set()):
                    continue
                candidates = []
                for doctor in self.doctors:
                    if iso in self.doctor_off.get(doctor.id, set()):
                        continue
                    # 禁止同日值班的組合
                    if self._violates_forbidden_pair(doctor.id, same_day_used):
                        continue
                    score = self._doctor_score(doctor, day, doctor_days, same_day_used, current_count)
                    if score[0] >= 10**9:
                        continue
                    candidates.append((score, doctor))
                if not candidates:
                    # 退而求其次：放寬間隔，但仍需符合特休、目標上限、同日/禁組合約束
                    for doctor in self.doctors:
                        if iso in self.doctor_off.get(doctor.id, set()):
                            continue
                        if doctor.id in same_day_used:
                            continue
                        if self._violates_forbidden_pair(doctor.id, same_day_used):
                            continue
                        # 絕對不能超過目標班數
                        if doctor.target_shifts is not None and current_count.get(doctor.id, 0) >= doctor.target_shifts:
                            continue
                        prev_days = sorted(doctor_days.get(doctor.id, []))
                        min_gap = 999 if not prev_days else min(abs(day - x) for x in prev_days)
                        if min_gap < 1:
                            continue
                        candidates.append(((1000, 0, 0, current_count.get(doctor.id, 0), doctor.name), doctor))
                if not candidates:
                    unfilled.append({'ward_id': ward.id, 'ward_name': ward.name, 'day': day, 'reason': '無可用醫師'})
                    continue
                candidates.sort(key=lambda x: x[0])
                chosen = candidates[0][1]
                assignments[ward.id][day] = chosen.id
                same_day_used.add(chosen.id)
                doctor_days[chosen.id].append(day)
                current_count[chosen.id] += 1

        return {
            'year': year,
            'month': month,
            'assignments': assignments,
            'doctor_shift_count': current_count,
            'unfilled': unfilled,
            'month_meta': self.month_meta(year, month),
        }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/next-month')
def api_next_month():
    s = DutyScheduler([], [], {}, {}, {})
    y, m = s.next_month()
    return jsonify({'year': y, 'month': m})

@app.route('/api/schedule', methods=['POST'])
def api_schedule():
    data = request.get_json(force=True)
    doctors = [Doctor(**d) for d in data.get('doctors', [])]
    wards = [Ward(**w) for w in data.get('wards', [])]
    doctor_off = {k: set(v) for k, v in data.get('doctor_off', {}).items()}
    ward_off = {k: set(v) for k, v in data.get('ward_off', {}).items()}
    manual_holidays = data.get('manual_holidays', {})
    fixed_assignments = data.get('fixed_assignments', {})
    # 新增：不能同日值班組別
    raw_pairs = data.get('forbidden_pairs', [])
    forbidden_pairs = []
    for p in raw_pairs:
        a = p.get('a')
        b = p.get('b')
        if a and b and a != b:
            forbidden_pairs.append((a, b))
    year = int(data['year'])
    month = int(data['month'])
    scheduler = DutyScheduler(doctors, wards, doctor_off, ward_off, manual_holidays, fixed_assignments, forbidden_pairs)
    result = scheduler.generate(year, month)
    return jsonify(result)

@app.route('/api/holidays', methods=['POST'])
def api_holidays():
    data = request.get_json(force=True)
    year = int(data['year'])
    month = int(data['month'])
    s = DutyScheduler([], [], {}, {}, {})
    return jsonify({'month_meta': s.month_meta(year, month), 'taiwan_holidays_enabled': TW_HOLIDAY_AVAILABLE})

if __name__ == '__main__':
    import threading, webbrowser
    def _open_browser():
        try:
            webbrowser.open('http://127.0.0.1:5000/')
        except Exception:
            pass
    threading.Timer(1.0, _open_browser).start()
    app.run(debug=False, port=5000)
