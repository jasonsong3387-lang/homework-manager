import json
import os
import socket
import time
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

# 데이터 파일 경로
DATA_FILE = "homework_data.json"

# 기본 데이터 세팅 (송지유, 송지안 다자녀 기반 구조)
DEFAULT_DATA = {
    "children": {
        "송지유 🧑": {
            "reward_minutes": 0,
            "subjects": {
                "📖 국어": [
                    {"title": "교과서 3단원 읽기", "completed": False, "approved": False, "reward_minutes": 15},
                    {"title": "받아쓰기 틀린 단어 3번 쓰기", "completed": False, "approved": False, "reward_minutes": 15}
                ],
                "🧮 수학": [
                    {"title": "수학 익힘책 10-12쪽 풀기", "completed": False, "approved": False, "reward_minutes": 15}
                ]
            },
            "pending_rewards": [],
            "used_rewards_today": []  # 오늘 하루 동안 최종 사용(승인) 완료된 보상 목록
        },
        "송지안 👧": {
            "reward_minutes": 0,
            "subjects": {
                "🔤 영어": [
                    {"title": "영어 단어 10개 외우기", "completed": False, "approved": False, "reward_minutes": 15}
                ],
                "🎨 예체능/기타": [
                    {"title": "리코더 연습 10분", "completed": False, "approved": False, "reward_minutes": 15}
                ]
            },
            "pending_rewards": [],
            "used_rewards_today": []  # 오늘 하루 동안 최종 사용(승인) 완료된 보상 목록
        }
    }
}

def load_data():
    """JSON 파일에서 데이터를 로드하고 안전하게 데이터 구조를 지유, 지안 규격으로 변환(Migration)합니다."""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                
                # 구형 데이터 마이그레이션 및 필드 동기화
                if "children" not in data:
                    data = DEFAULT_DATA
                
                # '첫째', '둘째' 한글 이름 임시 매핑 대응
                if "첫째 🧑" in data["children"]:
                    data["children"]["송지유 🧑"] = data["children"].pop("첫째 🧑")
                if "둘째 👧" in data["children"]:
                    data["children"]["송지안 👧"] = data["children"].pop("둘째 👧")
                
                # 하위 자녀 데이터 필드 동기화 보완
                for child_name, child_data in data["children"].items():
                    if "reward_minutes" not in child_data:
                        child_data["reward_minutes"] = 0
                    if "subjects" not in child_data:
                        child_data["subjects"] = {}
                    if "pending_rewards" not in child_data:
                        child_data["pending_rewards"] = []
                    if "used_rewards_today" not in child_data:
                        child_data["used_rewards_today"] = []
                        
                    for subj, tasks in child_data["subjects"].items():
                        for task in tasks:
                            if "approved" not in task:
                                task["approved"] = task.get("completed", False)
                            if "reward_minutes" not in task:
                                task["reward_minutes"] = 15
                return data
        except Exception:
            return DEFAULT_DATA
    else:
        save_data(DEFAULT_DATA)
        return DEFAULT_DATA

def save_data(data):
    """데이터를 JSON 파일에 저장합니다."""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"데이터 저장 실패: {e}")

# FastAPI 인스턴스 생성
app = FastAPI(title="초등 스스로 다자녀 숙제방 API")

# --- API 입출력 모델 선언 (Pydantic) ---
class PinVerifyRequest(BaseModel):
    pin: str

class ChildRequest(BaseModel):
    name: str

class SubjectRequest(BaseModel):
    child: str
    name: str

class TaskAddRequest(BaseModel):
    child: str
    subject: str
    title: str
    reward_minutes: int = 15

class TaskActionRequest(BaseModel):
    child: str
    subject: str
    index: int

class RewardUseRequest(BaseModel):
    child: str
    minutes: int
    name: str

class RewardActionRequest(BaseModel):
    child: str
    id: float


# --- HTML 반응형 싱글 파일 템플릿 (Tailwind + Vue.js 3 + SweetAlert2) ---
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>🌟 지유 & 지안 스스로 숙제방 & 보상 🌟</title>
    <!-- Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- SweetAlert2 (예쁜 알림창) -->
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
    <!-- FontAwesome 이모티콘 -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <!-- Vue 3 CDN -->
    <script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Gaegu:wght@700&family=Nanum+Gothic:wght@400;700;800&display=swap');
        body {
            font-family: 'Nanum Gothic', sans-serif;
            background-color: #FFFDF9;
        }
        .kids-title {
            font-family: 'Gaegu', sans-serif;
        }
        .completed-task {
            text-decoration: line-through;
            color: #9CA3AF;
        }
        [v-cloak] { display: none; }
    </style>
</head>
<body class="min-h-screen pb-12 text-slate-800">

    <div id="app" v-cloak>
        <!-- 1. 상단 헤더 -->
        <header class="bg-white border-b border-amber-100 shadow-sm sticky top-0 z-50 px-4 py-3">
            <div class="max-w-4xl mx-auto flex justify-between items-center">
                <h1 class="text-xl md:text-2xl font-black text-amber-600 flex items-center gap-2 kids-title">
                    <span>✨ 스스로 숙제방 ✨</span>
                </h1>
                
                <div class="flex items-center gap-2">
                    <!-- 현재 모드 표시 뱃지 -->
                    <span class="text-xs md:text-sm font-bold px-3 py-1.5 rounded-full shadow-inner animate-pulse"
                          :class="isAdmin ? 'bg-purple-100 text-purple-700' : 'bg-sky-100 text-sky-700'">
                        {{ isAdmin ? '👨‍👩‍👧‍👦 엄빠 모드' : '🧒 아이들 모드' }}
                    </span>
                    
                    <!-- 모드 토글 버튼 -->
                    <button v-if="!isAdmin" @click="switchToAdmin" class="bg-purple-500 hover:bg-purple-600 active:scale-95 transition-all text-white font-bold text-xs md:text-sm px-3 py-2 rounded-full shadow-md flex items-center gap-1">
                        <i class="fa-solid fa-lock"></i> 엄빠 로그인
                    </button>
                    <button v-else @click="switchToKids" class="bg-sky-500 hover:bg-sky-600 active:scale-95 transition-all text-white font-bold text-xs md:text-sm px-3 py-2 rounded-full shadow-md flex items-center gap-1">
                        <i class="fa-solid fa-child"></i> 아이들 모드로
                    </button>
                </div>
            </div>
        </header>

        <main class="max-w-4xl mx-auto px-4 mt-4">
            
            <!-- 🧑‍🤝‍🧑 아이 선택 탭 -->
            <section class="mb-6 flex flex-wrap items-center justify-between gap-4 bg-white p-3 rounded-2xl border border-slate-100 shadow-sm">
                <div class="flex items-center gap-1.5 overflow-x-auto pb-1 md:pb-0">
                    <span class="text-xs font-bold text-slate-400 mr-1 flex-shrink-0"><i class="fa-solid fa-users"></i> 우리 아이 방 :</span>
                    <button v-for="childName in childList" :key="childName" 
                            @click="selectChild(childName)"
                            class="px-4 py-2 rounded-full font-black text-xs md:text-sm transition-all duration-300"
                            :class="selectedChild === childName ? 'bg-amber-400 text-slate-800 scale-105 shadow-md' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'">
                        {{ childName }}
                    </button>
                </div>
                
                <!-- 엄빠용 아이 관리 메뉴 -->
                <div v-if="isAdmin" class="flex gap-2">
                    <button @click="addChild" class="bg-emerald-100 hover:bg-emerald-200 text-emerald-700 font-bold text-xs px-3 py-2 rounded-xl transition-all flex items-center gap-1">
                        <i class="fa-solid fa-user-plus"></i> 아이 추가
                    </button>
                    <button @click="deleteChild" class="bg-rose-100 hover:bg-rose-200 text-rose-700 font-bold text-xs px-3 py-2 rounded-xl transition-all flex items-center gap-1">
                        <i class="fa-solid fa-user-minus"></i> 아이 삭제
                    </button>
                </div>
            </section>

            <!-- 🎁 선택된 아이의 내가 모은 자유 시간 현황 패널 -->
            <section class="bg-gradient-to-r from-amber-100 to-yellow-50 border-2 border-amber-200 rounded-3xl p-4 md:p-6 shadow-md mb-6 relative overflow-hidden">
                <div class="absolute -right-6 -bottom-6 text-amber-200 opacity-40 text-8xl pointer-events-none">
                    <i class="fa-solid fa-gift"></i>
                </div>
                
                <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div>
                        <h2 class="text-amber-800 font-extrabold text-sm md:text-base flex items-center gap-1.5">
                            <i class="fa-solid fa-ribbon text-rose-500"></i> [ {{ selectedChild }} ] 의 칭찬 자유 시간 전광판
                        </h2>
                        <div class="text-3xl md:text-4xl font-black text-amber-600 mt-1 kids-title">
                            ⏰ {{ activeChildData.reward_minutes }} 분
                            <!-- 사용 대기 알림 뱃지 -->
                            <span v-if="activeChildData.pending_rewards.length > 0" class="text-xs bg-rose-100 border border-rose-300 text-rose-600 font-bold px-2 py-1 rounded-lg ml-2 animate-bounce inline-block align-middle">
                                🔔 허락 대기중 {{ totalPendingMinutes }}분
                            </span>
                        </div>
                    </div>
                    
                    <div class="bg-white/80 backdrop-blur-sm rounded-2xl p-3 border border-amber-200/50">
                        <p class="text-xs font-bold text-slate-500 mb-2 flex items-center gap-1 justify-end">
                            <i class="fa-solid fa-ticket-simple text-amber-500"></i> 시간 쿠폰 신청하기
                        </p>
                        <div class="flex flex-wrap gap-2 justify-end">
                            <button @click="requestUseReward(5, '게임하기 🎮')" class="bg-rose-400 hover:bg-rose-500 text-white font-bold text-xs px-3 py-2 rounded-xl active:scale-95 transition-all shadow-sm">
                                🎮 게임 5분
                            </button>
                            <button @click="requestUseReward(5, '영상보기 📺')" class="bg-indigo-400 hover:bg-indigo-500 text-white font-bold text-xs px-3 py-2 rounded-xl active:scale-95 transition-all shadow-sm">
                                📺 영상 5분
                            </button>
                            <button @click="requestCustomReward" class="bg-slate-500 hover:bg-slate-600 text-white font-bold text-xs px-3 py-2 rounded-xl active:scale-95 transition-all shadow-sm">
                                ⚙️ 직접 입력
                            </button>
                        </div>
                    </div>
                </div>
            </section>

            <!-- 🔔 2-1. 통합 숙제 완료 승인 대기 목록 (엄빠 모드일 때 최상단에 일괄 표시!) -->
            <section v-if="isAdmin && allPendingTasks.length > 0" class="bg-amber-50 border border-amber-300 rounded-3xl p-4 shadow-sm mb-6">
                <h3 class="font-bold text-amber-800 text-sm md:text-base flex items-center gap-1.5 mb-3">
                    <i class="fa-solid fa-bell text-amber-600 animate-bounce"></i> 
                    📢 아이들이 숙제를 마쳤어요! 완료 승인을 해주세요!
                </h3>
                
                <div class="space-y-2">
                    <div v-for="item in allPendingTasks" :key="item.child + '-' + item.subject + '-' + item.index" class="flex items-center justify-between bg-white p-3 rounded-2xl border border-amber-100 shadow-sm">
                        <div class="flex items-center gap-2 text-xs md:text-sm font-semibold text-slate-700">
                            <span class="bg-purple-100 text-purple-800 px-2 py-0.5 rounded-lg text-[10px] font-black">{{ item.child }}</span>
                            <span class="bg-amber-100 text-amber-800 px-2 py-0.5 rounded-lg text-[10px] font-black">{{ item.subject }}</span>
                            <span class="truncate max-w-[150px] md:max-w-none">{{ item.title }}</span>
                            <span class="text-[10px] text-emerald-600 font-extrabold bg-emerald-50 border border-emerald-100 px-1.5 py-0.5 rounded-md flex-shrink-0">+{{ item.reward_minutes }}분</span>
                        </div>
                        
                        <button @click="approveTask(item.child, item.subject, item.index)" class="bg-emerald-500 hover:bg-emerald-600 text-white font-extrabold text-xs px-3 py-1.5 rounded-full active:scale-95 transition-all shadow-sm flex-shrink-0">
                            승인 👍
                        </button>
                    </div>
                </div>
            </section>

            <!-- 🎫 3. 통합 시간 사용 신청 대기 목록 (모든 아이들의 대기 중인 사용 요청들을 한눈에 일괄 처리) -->
            <section v-if="allPendingRewards.length > 0" class="bg-rose-50/70 border border-rose-200 rounded-3xl p-4 shadow-sm mb-6">
                <h3 class="font-bold text-rose-800 text-sm md:text-base flex items-center gap-1.5 mb-3">
                    <i class="fa-solid fa-hourglass-start animate-spin"></i> 
                    {{ isAdmin ? '📢 아이들이 시간 쿠폰을 허락해 달래요!' : '🎫 쿠폰 사용 승인을 기다리고 있는 대기열' }}
                </h3>
                
                <div class="space-y-2">
                    <div v-for="item in allPendingRewards" :key="item.child + '-' + item.id" class="flex items-center justify-between bg-white p-3 rounded-2xl border border-rose-100 shadow-sm">
                        <div class="flex items-center gap-2 text-xs md:text-sm font-semibold text-slate-700">
                            <span class="bg-purple-100 text-purple-800 px-2 py-0.5 rounded-lg text-[10px] font-black">{{ item.child }}</span>
                            <span class="bg-rose-100 text-rose-600 px-2 py-0.5 rounded-lg text-[10px] font-black">{{ item.minutes }}분</span>
                            <span>{{ item.name }}</span>
                        </div>
                        
                        <div class="flex items-center gap-2">
                            <!-- 엄빠 모드일 때만 허락/반려 제어 가능 -->
                            <div v-if="isAdmin" class="flex gap-1">
                                <button @click="approveRewardUse(item.child, item.id)" class="bg-emerald-500 hover:bg-emerald-600 text-white font-extrabold text-xs px-3 py-1.5 rounded-full active:scale-95 transition-all">
                                    허락 👍
                                </button>
                                <button @click="rejectRewardUse(item.child, item.id)" class="bg-rose-500 hover:bg-rose-600 text-white font-extrabold text-xs px-3 py-1.5 rounded-full active:scale-95 transition-all">
                                    거절 ❌
                                </button>
                            </div>
                            <!-- 아이들 모드일 때 대기 문구 -->
                            <span v-else class="text-xs text-rose-500 font-bold bg-rose-50 px-2.5 py-1 rounded-full border border-rose-100">
                                허락 대기중 ⏳
                            </span>
                        </div>
                    </div>
                </div>
            </section>

            <!-- 4. 🛠️ 엄빠 전용 관리 메뉴 -->
            <section v-if="isAdmin" class="bg-purple-50 border-2 border-purple-100 rounded-3xl p-4 shadow-sm mb-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div class="flex items-center gap-2">
                    <span class="bg-purple-500 text-white p-2 rounded-full"><i class="fa-solid fa-toolbox"></i></span>
                    <div>
                        <h3 class="font-bold text-purple-900 text-sm md:text-base">엄빠 전용 관리 메뉴</h3>
                        <p class="text-xs text-purple-600">과목 생성과 숙제 추가, 완료 승인을 조율합니다.</p>
                    </div>
                </div>
                <button @click="addSubject" class="bg-purple-600 hover:bg-purple-700 active:scale-95 transition-all text-white font-bold text-xs md:text-sm px-4 py-2.5 rounded-full shadow-md flex items-center gap-1.5 self-start md:self-auto">
                    <i class="fa-solid fa-folder-plus"></i> [ {{ selectedChild }} ] 의 과목 만들기
                </button>
            </section>

            <!-- 5. 📚 [ 선택된 아이 ] 의 과목별 숙제 카드 리스트 -->
            <section class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div v-for="(tasks, subjName, index) in activeChildData.subjects" :key="subjName" class="bg-white rounded-3xl border border-slate-100 shadow-sm overflow-hidden flex flex-col justify-between">
                    <div class="p-4 border-b flex items-center justify-between" :class="getHeaderStyle(index)">
                        <div class="flex items-center gap-1 font-black text-sm md:text-base">
                            <span>{{ subjName }}</span>
                            <!-- 남은 숙제 개수 -->
                            <span v-if="getPendingCount(tasks) > 0" class="bg-rose-500 text-white text-[10px] font-black px-2 py-0.5 rounded-full ml-1">
                                {{ getPendingCount(tasks) }}
                            </span>
                            <span v-else class="bg-emerald-500 text-white text-[10px] font-black px-2 py-0.5 rounded-full ml-1">
                                완료! 🎉
                            </span>
                        </div>
                        <div class="flex gap-1.5">
                            <!-- 과목 삭제는 엄빠 전용 -->
                            <button v-if="isAdmin" @click="deleteSubject(subjName)" class="text-slate-400 hover:text-rose-600 p-1 text-xs transition-all" title="과목 삭제">
                                <i class="fa-solid fa-trash-can"></i>
                            </button>
                            <!-- 숙제 추가는 아이들도 상시 추가 가능! -->
                            <button @click="addTask(subjName)" class="font-bold text-xs px-2.5 py-1 rounded-full transition-all flex items-center gap-0.5" :class="getBtnStyle(index)">
                                <i class="fa-solid fa-plus"></i> 숙제 추가
                            </button>
                        </div>
                    </div>

                    <!-- 숙제 리스트 바디 -->
                    <div class="p-4 space-y-2 flex-grow">
                        <p v-if="tasks.length === 0" class="text-xs text-slate-400 italic py-4 text-center">
                            등록된 숙제가 없어요. 우측의 [+ 숙제 추가] 버튼을 눌러보세요! 😊
                        </p>
                        <div v-else v-for="(task, taskIdx) in tasks" :key="taskIdx" class="flex items-center justify-between p-2 hover:bg-slate-50 rounded-2xl transition-all">
                            <div class="flex items-center gap-2 max-w-[70%]">
                                <i v-if="task.completed && task.approved" class="fa-solid fa-circle-check text-emerald-500"></i>
                                <i v-elif="task.completed && !task.approved" class="fa-solid fa-hourglass-half text-amber-500 animate-spin"></i>
                                <i v-else class="fa-regular fa-star text-amber-400"></i>
                                
                                <span class="text-xs md:text-sm break-all font-semibold" :class="getTaskTextClass(task)">
                                    {{ task.title }}
                                    <span class="text-[9px] text-emerald-600 font-extrabold bg-emerald-50 border border-emerald-100 px-1.5 py-0.5 rounded-md ml-1">+{{ task.reward_minutes }}분</span>
                                </span>
                            </div>
                            
                            <div class="flex items-center gap-1">
                                <!-- 1. 완료 신청 체크 -->
                                <button v-if="!task.completed" @click="completeTask(subjName, taskIdx)" class="bg-amber-400 hover:bg-amber-500 text-slate-800 font-extrabold text-[11px] px-2.5 py-1 rounded-full shadow-sm active:scale-95 transition-all">
                                    완료 🌟
                                </button>
                                <span v-if="!isAdmin && task.completed && !task.approved" class="text-[10px] text-amber-600 font-bold bg-amber-50 border border-amber-100 px-2 py-0.5 rounded-full">
                                    승인 대기⏳
                                </span>
                                
                                <!-- 2. 엄빠 모드: 완료 최종 승인 -->
                                <button v-if="isAdmin && task.completed && !task.approved" @click="approveTask(selectedChild, subjName, taskIdx)" class="bg-emerald-500 hover:bg-emerald-600 text-white font-extrabold text-[11px] px-2.5 py-1 rounded-full shadow-sm active:scale-95 transition-all">
                                    승인 👍
                                </button>
                                
                                <!-- 3. 엄빠 모드: 개별 삭제 -->
                                <button v-if="isAdmin" @click="deleteTask(subjName, taskIdx)" class="text-slate-300 hover:text-rose-500 p-1 text-xs transition-all">
                                    <i class="fa-solid fa-trash-can"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            <!-- 📅 6. 선택된 아이의 [오늘의 보상 사용 기록 (Daily 사용 목록)] -->
            <section class="mt-6 bg-white border border-slate-100 rounded-3xl p-4 md:p-6 shadow-sm">
                <h3 class="font-extrabold text-slate-700 text-sm md:text-base flex items-center gap-2 mb-3">
                    <i class="fa-solid fa-calendar-day text-amber-500"></i>
                    📅 [ {{ selectedChild }} ] 의 오늘 하루 보상 사용 기록
                </h3>
                
                <div v-if="!activeChildData.used_rewards_today || activeChildData.used_rewards_today.length === 0" class="text-center py-6 text-xs text-slate-400 italic">
                    오늘 사용한 자유 시간이 아직 없어요. 숙제를 열심히 완료하고 쿠폰을 신청해 보세요! 😄
                </div>
                
                <div v-else class="relative border-l border-amber-200 ml-3.5 space-y-4">
                    <div v-for="log in activeChildData.used_rewards_today" :key="log.timestamp" class="relative pl-6">
                        <!-- 타임라인 아이콘 지점 -->
                        <div class="absolute -left-2 top-1.5 w-4.5 h-4.5 rounded-full bg-amber-400 border-2 border-white flex items-center justify-center">
                            <i class="fa-solid fa-check text-[7px] text-white"></i>
                        </div>
                        
                        <div class="text-xs text-slate-400 mb-0.5 font-bold">{{ log.time }}</div>
                        <div class="text-xs md:text-sm font-semibold text-slate-700 flex items-center gap-1.5">
                            <span class="bg-amber-100 text-amber-800 font-extrabold px-2 py-0.5 rounded-md text-[10px]">{{ log.minutes }}분 완료</span>
                            <span>{{ log.name }}</span>
                        </div>
                    </div>
                </div>
            </section>
        </main>
    </div>

    <script>
        const { createApp } = Vue;

        createApp({
            data() {
                return {
                    isAdmin: false,          // 기본 화면 모드: 아이들 모드
                    selectedChild: '',       // 선택된 아이 이름
                    childrenData: {},        // 전체 아이들의 데이터 컨테이너
                    headerColors: [
                        "bg-rose-50 border-rose-100 text-rose-800",
                        "bg-emerald-50 border-emerald-100 text-emerald-800",
                        "bg-sky-50 border-sky-100 text-sky-800",
                        "bg-amber-50 border-amber-100 text-amber-800",
                        "bg-purple-50 border-purple-100 text-purple-800",
                        "bg-cyan-50 border-cyan-100 text-cyan-800"
                    ],
                    btnColors: [
                        "text-rose-600 bg-rose-100 hover:bg-rose-200",
                        "text-emerald-600 bg-emerald-100 hover:bg-emerald-200",
                        "text-sky-600 bg-sky-100 hover:bg-sky-200",
                        "text-amber-600 bg-amber-100 hover:bg-amber-200",
                        "text-purple-600 bg-purple-100 hover:bg-purple-200",
                        "text-cyan-600 bg-cyan-100 hover:bg-cyan-200"
                    ]
                }
            },
            computed: {
                // 아이 목록 취합
                childList() {
                    return Object.keys(this.childrenData);
                },
                // 선택된 아이의 전체 정보 반환
                activeChildData() {
                    return this.childrenData[this.selectedChild] || { reward_minutes: 0, subjects: {}, pending_rewards: [], used_rewards_today: [] };
                },
                // 해당 아이의 승인 대기 중인 사용 요청들의 분 합계
                totalPendingMinutes() {
                    return (this.activeChildData.pending_rewards || []).reduce((sum, item) => sum + item.minutes, 0);
                },
                // 모든 아이들의 완료 승인 대기 상태인 숙제를 통합 취합 (엄빠 대시보드용)
                allPendingTasks() {
                    const list = [];
                    for (const [childName, data] of Object.entries(this.childrenData)) {
                        for (const [subjName, tasks] of Object.entries(data.subjects)) {
                            tasks.forEach((task, idx) => {
                                if (task.completed && !task.approved) {
                                    list.push({
                                        child: childName,
                                        subject: subjName,
                                        index: idx,
                                        title: task.title,
                                        reward_minutes: task.reward_minutes || 15
                                    });
                                }
                            });
                        }
                    }
                    return list;
                },
                // 모든 아이들의 사용 허락 대기 상태인 보상 통합 취합 (엄빠 대시보드용)
                allPendingRewards() {
                    const list = [];
                    for (const [childName, data] of Object.entries(this.childrenData)) {
                        (data.pending_rewards || []).forEach(item => {
                            list.push({
                                child: childName,
                                id: item.id,
                                minutes: item.minutes,
                                name: item.name
                            });
                        });
                    }
                    return list;
                }
            },
            mounted() {
                this.fetchData(true);
                // 5초마다 주기적으로 다른 브라우저의 업데이트 상황 실시간 패치
                setInterval(() => this.fetchData(false), 5000);
            },
            methods: {
                // 데이터 비동기 조회
                async fetchData(firstLoad = false) {
                    try {
                        const response = await fetch('/api/data');
                        const data = await response.json();
                        this.childrenData = data.children || {};
                        
                        // 첫 로딩 시, 기본 첫 번째 아이를 선택 처리
                        if (firstLoad && this.childList.length > 0) {
                            this.selectedChild = this.childList[0];
                        }
                    } catch (error) {
                        console.error("실시간 동기화 에러:", error);
                    }
                },
                // 아이 탭 클릭
                selectChild(childName) {
                    this.selectedChild = childName;
                },
                // 엄빠 로그인 인증 및 전환
                async switchToAdmin() {
                    const { value: pin } = await Swal.fire({
                        title: '🔒 엄빠 모드 로그인',
                        text: 'PIN 비밀번호 4자리를 입력하세요.',
                        input: 'password',
                        inputPlaceholder: '비밀번호(기본: 0000) 입력',
                        inputAttributes: {
                            maxlength: '4',
                            autocapitalize: 'off',
                            autocorrect: 'off'
                        },
                        showCancelButton: true,
                        confirmButtonText: '확인',
                        cancelButtonText: '취소',
                        confirmButtonColor: '#8B5CF6'
                    });

                    if (pin) {
                        const response = await fetch('/api/verify-pin', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ pin: pin })
                        });
                        const result = await response.json();
                        
                        if (result.success) {
                            this.isAdmin = true;
                            Swal.fire({
                                title: '엄빠 모드로 변경 완료!',
                                text: '다자녀 숙제 및 쿠폰 일괄 통합 관리판이 활성화되었습니다.',
                                icon: 'success',
                                timer: 1500,
                                showConfirmButton: false
                            });
                            this.fetchData();
                        } else {
                            Swal.fire('인증 실패 😭', result.message, 'error');
                        }
                    }
                },
                // 아이들 화면으로 전환
                switchToKids() {
                    this.isAdmin = false;
                    Swal.fire({
                        title: '아이들 모드 전환',
                        text: '열심히 공부하고 칭찬 자유 시간을 차곡차곡 받아보세요!',
                        icon: 'info',
                        timer: 1500,
                        showConfirmButton: false
                    });
                    this.fetchData();
                },
                // 동적 아이 추가 (엄빠 모드 전용)
                async addChild() {
                    const { value: name } = await Swal.fire({
                        title: '🧒 아이 등록하기',
                        text: '아이의 이름 또는 닉네임을 적어주세요.',
                        input: 'text',
                        inputPlaceholder: '예: 첫째 민우 🧑, 둘째 수지 👧',
                        showCancelButton: true,
                        confirmButtonText: '추가',
                        cancelButtonText: '취소',
                        confirmButtonColor: '#10B981',
                        inputValidator: (value) => {
                            if (!value || !value.trim()) {
                                return '공백은 등록할 수 없습니다!';
                            }
                        }
                    });

                    if (name) {
                        const response = await fetch('/api/child/add', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ name: name.trim() })
                        });
                        const result = await response.json();
                        if (result.success) {
                            this.selectedChild = name.trim();
                            this.fetchData();
                        } else {
                            Swal.fire('경고', result.message, 'warning');
                        }
                    }
                },
                // 동적 아이 삭제 (엄빠 모드 전용)
                async deleteChild() {
                    const target = this.selectedChild;
                    const result = await Swal.fire({
                        title: '정말 삭제하시겠습니까?',
                        text: `[${target}] 아이의 방을 완전히 폐쇄하며 관련된 모든 숙제 및 보상 누적 시간이 영구 파괴됩니다!`,
                        icon: 'warning',
                        showCancelButton: true,
                        confirmButtonText: '네, 삭제할래요',
                        cancelButtonText: '취소',
                        confirmButtonColor: '#EF4444'
                    });

                    if (result.isConfirmed) {
                        const response = await fetch('/api/child/delete', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ name: target })
                        });
                        const res = await response.json();
                        if (res.success) {
                            const survived = this.childList.filter(c => c !== target);
                            this.selectedChild = survived.length > 0 ? survived[0] : '';
                            this.fetchData();
                        }
                    }
                },
                // 과목 추가
                async addSubject() {
                    const { value: name } = await Swal.fire({
                        title: `📂 [${this.selectedChild}] 과목 생성`,
                        input: 'text',
                        inputPlaceholder: '예: 📚 국어, 🎹 피아노, 📝 일기 등',
                        showCancelButton: true,
                        confirmButtonText: '추가',
                        cancelButtonText: '취소',
                        confirmButtonColor: '#10B981',
                        inputValidator: (value) => {
                            if (!value || !value.trim()) {
                                return '과목명을 입력해 주세요!';
                            }
                        }
                    });

                    if (name) {
                        const response = await fetch('/api/subject/add', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ child: this.selectedChild, name: name.trim() })
                        });
                        const result = await response.json();
                        if (result.success) {
                            this.fetchData();
                        } else {
                            Swal.fire('경고', result.message, 'warning');
                        }
                    }
                },
                // 과목 삭제
                async deleteSubject(name) {
                    const result = await Swal.fire({
                        title: '과목 삭제',
                        text: `[${name}] 안의 모든 숙제도 파괴됩니다. 삭제할까요?`,
                        icon: 'warning',
                        showCancelButton: true,
                        confirmButtonText: '네, 삭제',
                        cancelButtonText: '취소',
                        confirmButtonColor: '#EF4444'
                    });

                    if (result.isConfirmed) {
                        await fetch('/api/subject/delete', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ child: this.selectedChild, name })
                        });
                        this.fetchData();
                    }
                },
                // 숙제 추가
                async addTask(subjName) {
                    const { value: formValues } = await Swal.fire({
                        title: `➕ [${subjName}] 숙제 추가`,
                        html:
                            '<input id="swal-input-title" class="swal2-input w-full p-2 border rounded-xl" placeholder="숙제 내용 입력 (예: 일기 쓰기)">' +
                            '<div class="mt-3 flex items-center justify-between px-3 text-slate-500 font-bold text-xs"><label for="swal-input-reward">완료 보상 시간(분):</label>' +
                            '<input id="swal-input-reward" type="number" value="15" class="swal2-input w-24 p-1 border rounded-lg text-center"></div>',
                        focusConfirm: false,
                        showCancelButton: true,
                        confirmButtonText: '숙제 등록',
                        cancelButtonText: '취소',
                        confirmButtonColor: '#3B82F6',
                        preConfirm: () => {
                            const title = document.getElementById('swal-input-title').value;
                            const reward = document.getElementById('swal-input-reward').value;
                            if (!title || !title.trim()) {
                                Swal.showValidationMessage('숙제 내용을 적어야 해요!');
                                return false;
                            }
                            return { title: title.trim(), reward: parseInt(reward) || 15 };
                        }
                    });

                    if (formValues) {
                        await fetch('/api/task/add', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                child: this.selectedChild,
                                subject: subjName,
                                title: formValues.title,
                                reward_minutes: formValues.reward
                            })
                        });
                        this.fetchData();
                    }
                },
                // 완료 체크 요청 (아이 시점)
                async completeTask(subjName, taskIdx) {
                    const response = await fetch('/api/task/complete', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ child: this.selectedChild, subject: subjName, index: taskIdx })
                    });
                    const result = await response.json();
                    if (result.success) {
                        Swal.fire({
                            title: '완료 체크 신청 완료! 🌟⏳',
                            text: '부모님께 승인요청을 보냈습니다. 엄빠가 승인하면 자유 시간이 모입니다!',
                            icon: 'success'
                        });
                        this.fetchData();
                    }
                },
                // 완료 최종 승인 (엄빠 전용 통합 알림판/개별 카드 공용 지원)
                async approveTask(childName, subjName, taskIdx) {
                    const response = await fetch('/api/task/approve', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ child: childName, subject: subjName, index: taskIdx })
                    });
                    const result = await response.json();
                    if (result.success) {
                        Swal.fire({
                            title: '최종 승인 완료! 👍',
                            text: `[${childName}] 의 약속한 보상 자유 시간이 정상 가산되었습니다.`,
                            icon: 'success',
                            timer: 2000,
                            showConfirmButton: false
                        });
                        this.fetchData();
                    }
                },
                // 숙제 제거
                async deleteTask(subjName, taskIdx) {
                    await fetch('/api/task/delete', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ child: this.selectedChild, subject: subjName, index: taskIdx })
                    });
                    this.fetchData();
                },
                // 자유시간 쿠폰 요청 신청 (아이 시점)
                async requestUseReward(minutes, name) {
                    const availableMinutes = this.activeChildData.reward_minutes - this.totalPendingMinutes;
                    if (availableMinutes < minutes) {
                        Swal.fire('시간이 부족해요 😭', '남은 시간 또는 이미 결제 대기중인 예약 시간이 부족합니다.', 'error');
                        return;
                    }

                    const result = await Swal.fire({
                        title: '쿠폰 사용 신청 🎫',
                        text: `[${name}] 쿠폰을 바꾸기 위해 엄빠에게 ${minutes}분 승인요청을 전송할까요?`,
                        icon: 'question',
                        showCancelButton: true,
                        confirmButtonText: '허락 요청하기',
                        cancelButtonText: '취소',
                        confirmButtonColor: '#EC4899'
                    });

                    if (result.isConfirmed) {
                        const response = await fetch('/api/reward/request', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ child: this.selectedChild, minutes, name })
                        });
                        const res = await response.json();
                        if (res.success) {
                            Swal.fire('요청 완료! ⏳', '엄빠의 스마트폰 알림 대기열로 즉시 전송되었습니다.', 'success');
                            this.fetchData();
                        }
                    }
                },
                // 커스텀 자유시간 직접 작성 신청
                async requestCustomReward() {
                    const { value: mins } = await Swal.fire({
                        title: '⚙️ 자유시간 직접 조율 신청',
                        input: 'number',
                        inputLabel: '신청하고 싶은 시간(분)을 입력해 주세요:',
                        inputPlaceholder: '예: 25, 35',
                        showCancelButton: true,
                        inputValidator: (value) => {
                            if (!value || isNaN(value) || parseInt(value) <= 0) {
                                return '1분 이상의 정수로 적어야 합니다!';
                            }
                        }
                    });

                    if (mins) {
                        const useMins = parseInt(mins);
                        const availableMinutes = this.activeChildData.reward_minutes - this.totalPendingMinutes;
                        
                        if (availableMinutes < useMins) {
                            Swal.fire('시간 부족 😭', `사용 가능한 보상 시간이 부족합니다. (대기 요청 포함)`, 'error');
                            return;
                        }

                        const { value: reason } = await Swal.fire({
                            title: '무엇을 하고 싶으신가요?',
                            input: 'text',
                            inputPlaceholder: '예: 보드게임 한 판 하기, 놀이터 다녀오기 등',
                            showCancelButton: true,
                            confirmButtonText: '요청 전송'
                        });

                        const finalReason = (reason && reason.trim()) ? reason.trim() : "자유시간 보상 신청";

                        const response = await fetch('/api/reward/request', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ child: this.selectedChild, minutes: useMins, name: finalReason })
                        });
                        const res = await response.json();
                        if (res.success) {
                            Swal.fire('신청 전송 성공! ⏳', `[${finalReason}] 승인 조율을 부모님께 요청했습니다.`, 'success');
                            this.fetchData();
                        }
                    }
                },
                // 쿠폰 사용 승인 허락 처리 (엄빠 전용)
                async approveRewardUse(childName, requestId) {
                    const response = await fetch('/api/reward/approve', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ child: childName, id: requestId })
                    });
                    const result = await response.json();
                    if (result.success) {
                        Swal.fire('허락 완료! 👍🎫', `[${childName}] 의 자유 시간 사용을 정상 승인 및 쿠폰 차감했습니다.`, 'success');
                        this.fetchData();
                    } else {
                        Swal.fire('오류', result.message, 'error');
                    }
                },
                // 쿠폰 사용 거절 처리 (엄빠 전용)
                async rejectRewardUse(childName, requestId) {
                    const response = await fetch('/api/reward/reject', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ child: childName, id: requestId })
                    });
                    const result = await response.json();
                    if (result.success) {
                        Swal.fire('요청 거절', '해당 보상 사용 요청을 안전하게 반려(취소)시켰습니다.', 'info');
                        this.fetchData();
                    }
                },
                // UI 헬퍼
                getPendingCount(tasks) {
                    return tasks.filter(t => !t.completed).length;
                },
                getHeaderStyle(index) {
                    return this.headerColors[index % this.headerColors.length];
                },
                getBtnStyle(index) {
                    return this.btnColors[index % this.btnColors.length];
                },
                getTaskTextClass(task) {
                    if (task.completed && task.approved) {
                        return 'completed-task text-slate-400 line-through';
                    } else if (task.completed && !task.approved) {
                        return 'text-amber-500 italic';
                    }
                    return 'text-slate-700';
                }
            }
        }).mount('#app');
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def read_root():
    return HTML_TEMPLATE

@app.get("/api/data")
def get_data():
    return load_data()

@app.post("/api/verify-pin")
def verify_pin(req: PinVerifyRequest):
    # 비밀번호는 기본 '1029'로 설정되어 있습니다. (원하는 비밀번호로 커스텀 가능)
    if req.pin == "1029":
        return {"success": True}
    return {"success": False, "message": "비밀번호가 올바르지 않습니다!"}

@app.post("/api/child/add")
def add_child(req: ChildRequest):
    data = load_data()
    name = req.name.strip()
    if not name:
        return {"success": False, "message": "올바른 이름을 넣어주세요."}
    if name in data["children"]:
        return {"success": False, "message": "이미 같은 이름의 자녀가 존재합니다!"}
    
    # 신규 자녀 빈 구성 생성
    data["children"][name] = {
        "reward_minutes": 0,
        "subjects": {
            "📖 국어": [],
            "🧮 수학": [],
            "🔤 영어": []
        },
        "pending_rewards": [],
        "used_rewards_today": []
    }
    save_data(data)
    return {"success": True}

@app.post("/api/child/delete")
def delete_child(req: ChildRequest):
    data = load_data()
    name = req.name.strip()
    if name in data["children"]:
        del data["children"][name]
        save_data(data)
        return {"success": True}
    return {"success": False, "message": "존재하지 않는 자녀입니다."}

@app.post("/api/subject/add")
def add_subject(req: SubjectRequest):
    data = load_data()
    child = req.child
    name = req.name.strip()
    if child not in data["children"]:
        return {"success": False, "message": "존재하지 않는 아이입니다."}
    if name in data["children"][child]["subjects"]:
        return {"success": False, "message": "이미 생성되어 있는 과목입니다!"}
    
    data["children"][child]["subjects"][name] = []
    save_data(data)
    return {"success": True}

@app.post("/api/subject/delete")
def delete_subject(req: SubjectRequest):
    data = load_data()
    child = req.child
    name = req.name.strip()
    if child in data["children"] and name in data["children"][child]["subjects"]:
        del data["children"][child]["subjects"][name]
        save_data(data)
        return {"success": True}
    return {"success": False, "message": "유효하지 않은 요청입니다."}

@app.post("/api/task/add")
def add_task(req: TaskAddRequest):
    data = load_data()
    child = req.child
    subject = req.subject
    title = req.title.strip()
    if child not in data["children"]:
        return {"success": False, "message": "존재하지 않는 아이입니다."}
    if subject not in data["children"][child]["subjects"]:
        return {"success": False, "message": "존재하지 않는 과목입니다."}
    
    data["children"][child]["subjects"][subject].append({
        "title": title,
        "completed": False,
        "approved": False,
        "reward_minutes": req.reward_minutes
    })
    save_data(data)
    return {"success": True}

@app.post("/api/task/complete")
def complete_task(req: TaskActionRequest):
    data = load_data()
    child = req.child
    subject = req.subject
    index = req.index
    if child not in data["children"] or subject not in data["children"][child]["subjects"]:
        return {"success": False, "message": "정보를 조회할 수 없습니다."}
    
    tasks = data["children"][child]["subjects"][subject]
    if index < 0 or index >= len(tasks):
        return {"success": False, "message": "인덱스 범위를 초과했습니다."}
    
    tasks[index]["completed"] = True
    tasks[index]["approved"] = False
    save_data(data)
    return {"success": True}

@app.post("/api/task/approve")
def approve_task(req: TaskActionRequest):
    data = load_data()
    child = req.child
    subject = req.subject
    index = req.index
    if child not in data["children"] or subject not in data["children"][child]["subjects"]:
        return {"success": False, "message": "정보를 조회할 수 없습니다."}
    
    tasks = data["children"][child]["subjects"][subject]
    if index < 0 or index >= len(tasks):
        return {"success": False, "message": "유효하지 않은 번호입니다."}
    
    task = tasks[index]
    if task["completed"] and not task["approved"]:
        task["approved"] = True
        data["children"][child]["reward_minutes"] += task.get("reward_minutes", 15)
        save_data(data)
        return {"success": True}
    return {"success": False, "message": "승인 가능한 항목이 아닙니다."}

@app.post("/api/task/delete")
def delete_task(req: TaskActionRequest):
    data = load_data()
    child = req.child
    subject = req.subject
    index = req.index
    if child in data["children"] and subject in data["children"][child]["subjects"]:
        tasks = data["children"][child]["subjects"][subject]
        if 0 <= index < len(tasks):
            tasks.pop(index)
            save_data(data)
            return {"success": True}
    return {"success": False, "message": "유효하지 않은 번호입니다."}

@app.post("/api/reward/request")
def request_reward(req: RewardUseRequest):
    data = load_data()
    child = req.child
    if child not in data["children"]:
        return {"success": False, "message": "존재하지 않는 아이입니다."}
    
    child_info = data["children"][child]
    total_pending = sum(item["minutes"] for item in child_info["pending_rewards"])
    available_mins = child_info["reward_minutes"] - total_pending
    
    if available_mins < req.minutes:
        return {"success": False, "message": "사용 가능한 칭찬 보상 시간이 부족합니다."}
    
    new_request = {
        "id": time.time(),
        "minutes": req.minutes,
        "name": req.name
    }
    child_info["pending_rewards"].append(new_request)
    save_data(data)
    return {"success": True}

@app.post("/api/reward/approve")
def approve_reward(req: RewardActionRequest):
    data = load_data()
    child = req.child
    req_id = req.id
    if child not in data["children"]:
        return {"success": False, "message": "존재하지 않는 아이입니다."}
    
    child_info = data["children"][child]
    request_item = next((item for item in child_info["pending_rewards"] if item["id"] == req_id), None)
    if not request_item:
        return {"success": False, "message": "해당 요청 건을 찾을 수 없습니다."}
    
    if child_info["reward_minutes"] < request_item["minutes"]:
        return {"success": False, "message": "칭찬 잔여 분량이 소진되어 승인할 수 없습니다."}
    
    # 시간 최종 차감
    child_info["reward_minutes"] -= request_item["minutes"]
    
    # [새 기능] Daily(오늘의 사용 목록) 기록 리스트에 데이터 주입
    local_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
    log_item = {
        "timestamp": time.time(),
        "time": local_time,
        "minutes": request_item["minutes"],
        "name": request_item["name"]
    }
    if "used_rewards_today" not in child_info:
        child_info["used_rewards_today"] = []
    child_info["used_rewards_today"].insert(0, log_item) # 최신 로그가 맨 위로 오도록 함
    
    # 대기 목록에서 지우기
    child_info["pending_rewards"] = [item for item in child_info["pending_rewards"] if item["id"] != req_id]
    save_data(data)
    return {"success": True}

@app.post("/api/reward/reject")
def reject_reward(req: RewardActionRequest):
    data = load_data()
    child = req.child
    req_id = req.id
    if child in data["children"]:
        child_info = data["children"][child]
        child_info["pending_rewards"] = [item for item in child_info["pending_rewards"] if item["id"] != req_id]
        save_data(data)
        return {"success": True}
    return {"success": False, "message": "요청 거절 실패."}

def get_local_ip():
    """서버컴퓨터의 현재 공유기 로컬 IP 주소를 자동 검출합니다."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

if __name__ == "__main__":
    import uvicorn
    port = 8000
    local_ip = get_local_ip()
    
    print("=" * 70)
    print("🎈 [다자녀 전용 스스로 숙제방] 공유 웹 서버 기동 완료!")
    print(f"🏠 PC(서버)에서 직접 열 때: http://localhost:{port}")
    print(f"📱 스마트폰/태블릿(엄마, 아빠, 아이들) 접속용 주소:")
    print(f"👉 http://{local_ip}:{port}")
    print("=" * 70)
    
    uvicorn.run(app, host="0.0.0.0", port=port)