/* ===== Sound Engine ===== */
const audioCtx = new (window.AudioContext || window.webkitAudioContext)();

function playCompleteSound() {
  // Resume context if suspended (browser autoplay policy)
  if (audioCtx.state === 'suspended') audioCtx.resume();

  const now = audioCtx.currentTime;

  // First tone — gentle rise
  const osc1 = audioCtx.createOscillator();
  const gain1 = audioCtx.createGain();
  osc1.type = 'sine';
  osc1.frequency.setValueAtTime(660, now);
  osc1.frequency.linearRampToValueAtTime(880, now + 0.06);
  gain1.gain.setValueAtTime(0, now);
  gain1.gain.linearRampToValueAtTime(0.3, now + 0.04);
  gain1.gain.linearRampToValueAtTime(0, now + 0.25);
  osc1.connect(gain1);
  gain1.connect(audioCtx.destination);
  osc1.start(now);
  osc1.stop(now + 0.25);

  // Second tone — satisfying chime
  const osc2 = audioCtx.createOscillator();
  const gain2 = audioCtx.createGain();
  osc2.type = 'sine';
  osc2.frequency.setValueAtTime(1320, now + 0.08);
  gain2.gain.setValueAtTime(0, now + 0.08);
  gain2.gain.linearRampToValueAtTime(0.25, now + 0.12);
  gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.5);
  osc2.connect(gain2);
  gain2.connect(audioCtx.destination);
  osc2.start(now + 0.08);
  osc2.stop(now + 0.5);
}

/* ===== Data Store ===== */
const STORAGE_KEY = 'todo_app_data';

function loadTasks() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveTasks(tasks) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(tasks));
}

/* ===== Helpers ===== */
function generateId() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
}

function formatDate(dateStr) {
  const today = new Date();
  const target = new Date(dateStr + 'T00:00:00');
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);

  const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];

  if (dateStr === today.toISOString().slice(0, 10)) return '今天';
  if (dateStr === yesterday.toISOString().slice(0, 10)) return '昨天';
  if (dateStr === tomorrow.toISOString().slice(0, 10)) return '明天';

  const month = target.getMonth() + 1;
  const day = target.getDate();
  const weekday = weekdays[target.getDay()];
  return `${month}月${day}日 ${weekday}`;
}

function formatDateShort(dateStr) {
  const parts = dateStr.split('-');
  return `${parseInt(parts[1])}/${parseInt(parts[2])}`;
}

/* ===== State ===== */
let tasks = loadTasks();
let currentFilter = 'all';
let selectedTag = 'study';

/* ===== DOM Elements ===== */
const $taskInput   = document.getElementById('taskInput');
const $addBtn      = document.getElementById('addBtn');
const $datePicker  = document.getElementById('datePicker');
const $taskList    = document.getElementById('taskList');
const $emptyState  = document.getElementById('emptyState');
const $filterTabs  = document.getElementById('filterTabs');
const $statTotal   = document.getElementById('statTotal');
const $statActive  = document.getElementById('statActive');
const $statDone    = document.getElementById('statDone');
const $tagChips    = document.querySelectorAll('.tag-chip');

// Set today as default date
$datePicker.value = new Date().toISOString().slice(0, 10);

/* ===== Render ===== */
function render() {
  // Apply filter
  let filtered = [...tasks];
  if (currentFilter === 'active') {
    filtered = filtered.filter(t => !t.completed);
  } else if (currentFilter === 'completed') {
    filtered = filtered.filter(t => t.completed);
  }

  // Sort: completed at bottom, then by date desc, then by creation time
  filtered.sort((a, b) => {
    if (a.completed !== b.completed) return a.completed ? 1 : -1;
    if (a.date !== b.date) return b.date.localeCompare(a.date);
    return b.createdAt - a.createdAt;
  });

  // Build HTML
  if (filtered.length === 0) {
    $taskList.innerHTML = '';
    $taskList.appendChild($emptyState);
    $emptyState.classList.remove('hidden');

    // Update empty message based on filter
    const emptyTitle = $emptyState.querySelector('.empty-title');
    const emptyDesc  = $emptyState.querySelector('.empty-desc');
    if (currentFilter === 'completed') {
      emptyTitle.textContent = '还没有完成的任务';
      emptyDesc.textContent = '完成一个任务，它会出现在这里';
    } else if (currentFilter === 'active') {
      emptyTitle.textContent = '太棒了！';
      emptyDesc.textContent = '所有任务都完成了';
    } else {
      emptyTitle.textContent = '还没有任务';
      emptyDesc.textContent = '添加你的第一个任务，开始高效的一天';
    }
  } else {
    $emptyState.classList.add('hidden');
    // Ensure empty state is not in the list
    if ($emptyState.parentNode === $taskList) {
      $emptyState.remove();
    }

    // Group by date
    const groups = new Map();
    filtered.forEach(t => {
      const key = t.date;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(t);
    });

    let html = '';
    groups.forEach((groupTasks, date) => {
      html += `
        <div class="date-header">
          <span class="date-header-text">${formatDate(date)}</span>
          <div class="date-header-line"></div>
        </div>
      `;
      groupTasks.forEach(t => {
        html += createTaskCard(t);
      });
    });

    $taskList.innerHTML = html;

    // Attach event listeners to cards
    $taskList.querySelectorAll('.task-card').forEach(card => {
      card.querySelector('.checkbox').addEventListener('click', (e) => {
        e.stopPropagation();
        toggleTask(card.dataset.id);
      });
      card.querySelector('.delete-btn').addEventListener('click', (e) => {
        e.stopPropagation();
        deleteTask(card.dataset.id);
      });
    });
  }

  // Update stats
  const total  = tasks.length;
  const active = tasks.filter(t => !t.completed).length;
  const done   = tasks.filter(t => t.completed).length;
  $statTotal.textContent  = total;
  $statActive.textContent = active;
  $statDone.textContent   = done;
}

function createTaskCard(task) {
  const tagNames = { study: '学习', work: '工作', personal: '生活' };
  const tagName = tagNames[task.tag] || task.tag;

  return `
    <div class="task-card ${task.completed ? 'completed' : ''}" data-id="${task.id}">
      <div class="checkbox">
        <svg width="12" height="10" viewBox="0 0 12 10" fill="none">
          <path d="M1 5l3 3 7-7" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
      <div class="task-content">
        <div class="task-title">${escapeHtml(task.title)}</div>
        <div class="task-meta">
          <span class="task-tag ${task.tag}">${tagName}</span>
          <span class="task-date">${formatDateShort(task.date)}</span>
        </div>
      </div>
      <button class="delete-btn" title="删除">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <path d="M3 3l8 8M11 3l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
      </button>
    </div>
  `;
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

/* ===== Actions ===== */
function addTask() {
  const title = $taskInput.value.trim();
  if (!title) return;

  const task = {
    id: generateId(),
    title,
    tag: selectedTag,
    date: $datePicker.value,
    completed: false,
    createdAt: Date.now(),
  };

  tasks.unshift(task);
  saveTasks(tasks);
  $taskInput.value = '';
  $taskInput.focus();
  render();
}

function toggleTask(id) {
  const task = tasks.find(t => t.id === id);
  if (!task) return;

  task.completed = !task.completed;

  if (task.completed) {
    playCompleteSound();
  }

  saveTasks(tasks);
  render();
}

function deleteTask(id) {
  const card = $taskList.querySelector(`[data-id="${id}"]`);
  if (card) {
    card.classList.add('removing');
    card.addEventListener('animationend', () => {
      tasks = tasks.filter(t => t.id !== id);
      saveTasks(tasks);
      render();
    }, { once: true });
  } else {
    tasks = tasks.filter(t => t.id !== id);
    saveTasks(tasks);
    render();
  }
}

function setFilter(filter) {
  currentFilter = filter;
  render();
}

/* ===== Event Listeners ===== */
$addBtn.addEventListener('click', addTask);

$taskInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') addTask();
});

$tagChips.forEach(chip => {
  chip.addEventListener('click', () => {
    $tagChips.forEach(c => c.classList.remove('selected'));
    chip.classList.add('selected');
    selectedTag = chip.dataset.tag;
  });
});

$filterTabs.addEventListener('click', (e) => {
  const tab = e.target.closest('.filter-tab');
  if (!tab) return;

  $filterTabs.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
  tab.classList.add('active');
  setFilter(tab.dataset.filter);
});

/* ===== Init ===== */
render();
$taskInput.focus();
