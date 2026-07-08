/* ====== Zs服药提醒智能体 - 前端脚本 ====== */

// Toast 通知
function showToast(msg, type = 'success') {
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.textContent = msg;
    toast.className = `toast ${type} show`;
    setTimeout(() => { toast.className = 'toast'; }, 3000);
}

// API 调用封装
async function api(url, options = {}) {
    try {
        const res = await fetch(url, {
            headers: { 'Content-Type': 'application/json', ...options.headers },
            ...options,
        });
        if (res.status === 401) {
            window.location.href = '/login';
            return null;
        }
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: '请求失败' }));
            throw new Error(err.detail || '请求失败');
        }
        return await res.json();
    } catch (e) {
        showToast(e.message, 'error');
        throw e;
    }
}

// ====== 认证 ======
async function handleRegister(e) {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.textContent = '注册中...';

    const data = {
        email: document.getElementById('email').value.trim(),
        password: document.getElementById('password').value,
        name: document.getElementById('name').value.trim(),
    };

    if (data.password.length < 6) {
        showToast('密码至少需要6个字符', 'error');
        btn.disabled = false;
        btn.textContent = '注册';
        return;
    }

    try {
        await api('/api/auth/register', {
            method: 'POST',
            body: JSON.stringify(data),
        });
        window.location.href = '/';
    } catch (e) {
        btn.disabled = false;
        btn.textContent = '注册';
    }
}

async function handleLogin(e) {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.textContent = '登录中...';

    const data = {
        email: document.getElementById('email').value.trim(),
        password: document.getElementById('password').value,
    };

    try {
        await api('/api/auth/login', {
            method: 'POST',
            body: JSON.stringify(data),
        });
        window.location.href = '/';
    } catch (e) {
        btn.disabled = false;
        btn.textContent = '登录';
    }
}

async function handleLogout() {
    await api('/api/auth/logout', { method: 'POST' });
    window.location.href = '/login';
}

// ====== 上传与 OCR 识别 ======
function setupUpload() {
    const zone = document.getElementById('uploadZone');
    const input = document.getElementById('fileInput');
    const preview = document.getElementById('uploadPreview');
    const previewImg = document.getElementById('previewImg');
    const ocrResult = document.getElementById('ocrResult');
    const loadingDiv = document.getElementById('uploadLoading');

    if (!zone || !input) return;

    zone.addEventListener('click', () => input.click());

    zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('dragover'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
    zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.classList.remove('dragover');
        if (e.dataTransfer.files.length) {
            input.files = e.dataTransfer.files;
            handleFileSelect();
        }
    });

    input.addEventListener('change', handleFileSelect);

    async function handleFileSelect() {
        const file = input.files[0];
        if (!file) return;

        // 预览
        const reader = new FileReader();
        reader.onload = (e) => {
            previewImg.src = e.target.result;
            preview.classList.add('show');
        };
        reader.readAsDataURL(file);

        // OCR识别
        loadingDiv.classList.add('show');
        ocrResult.classList.remove('show');

        const formData = new FormData();
        formData.append('file', file);

        try {
            const res = await fetch('/api/medicines/upload-recognize', {
                method: 'POST',
                body: formData,
            });

            if (res.status === 401) {
                window.location.href = '/login';
                return;
            }

            // 检查 content-type，避免把 HTML/plaintext 当 JSON 解析
            const contentType = res.headers.get('content-type') || '';
            if (!res.ok) {
                let errMsg = `服务器错误 (${res.status})`;
                if (contentType.includes('application/json')) {
                    const errJson = await res.json();
                    errMsg = errJson.detail || errMsg;
                } else {
                    const errText = await res.text();
                    // 提取纯文本错误（去除 HTML 标签）
                    errMsg = errText.replace(/<[^>]*>/g, '').trim().substring(0, 200) || errMsg;
                }
                throw new Error(errMsg);
            }

            if (!contentType.includes('application/json')) {
                throw new Error('服务器返回了非 JSON 格式');
            }

            const result = await res.json();

            document.getElementById('ocr_name').value = result.name || '';
            document.getElementById('ocr_specification').value = result.specification || '';
            document.getElementById('ocr_expiry_date').value = result.expiry_date || '';
            document.getElementById('ocr_description').value = result.description || '';
            // 只显示药品描述（不带 JSON）
            document.getElementById('ocr_raw_text').textContent = result.description || result.raw_text || '';
            document.getElementById('ocr_image_path').value = result.image_path || '';

            ocrResult.classList.add('show');
        } catch (e) {
            showToast('识别失败: ' + e.message, 'error');
        } finally {
            loadingDiv.classList.remove('show');
        }
    }
}

async function confirmMedicine(e) {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.textContent = '保存中...';

    // 直接使用 OCR 返回的 image_path（已由后端上传到 Supabase）
    const imagePath = document.getElementById('ocr_image_path').value || '';

    const data = {
        name: document.getElementById('ocr_name').value.trim(),
        specification: document.getElementById('ocr_specification').value.trim(),
        expiry_date: document.getElementById('ocr_expiry_date').value.trim(),
        description: document.getElementById('ocr_description').value.trim(),
        image_path: imagePath,
    };

    if (!data.name) {
        showToast('请输入药品名称', 'error');
        btn.disabled = false;
        btn.textContent = '确认识别结果并添加药品';
        return;
    }

    try {
        await api('/api/medicines', {
            method: 'POST',
            body: JSON.stringify(data),
        });
        showToast('药品添加成功！');
        setTimeout(() => { window.location.href = '/medicines'; }, 1000);
    } catch (e) {
        btn.disabled = false;
        btn.textContent = '确认识别结果并添加药品';
    }
}

// 手动添加药品
async function handleManualAdd(e) {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.textContent = '添加中...';

    const data = {
        name: document.getElementById('manual_name').value.trim(),
        specification: document.getElementById('manual_specification').value.trim(),
        expiry_date: document.getElementById('manual_expiry_date').value.trim(),
        description: document.getElementById('manual_description').value.trim(),
        image_path: '',
    };

    if (!data.name) {
        showToast('请输入药品名称', 'error');
        btn.disabled = false;
        btn.textContent = '添加药品';
        return;
    }

    try {
        await api('/api/medicines', {
            method: 'POST',
            body: JSON.stringify(data),
        });
        showToast('药品添加成功！');
        setTimeout(() => { window.location.href = '/medicines'; }, 1000);
    } catch (e) {
        btn.disabled = false;
        btn.textContent = '添加药品';
    }
}

// ====== 服药动作 ======
async function recordAction(recordId, action) {
    const now = new Date();
    const time = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;

    let delayMinutes = null;
    if (action === 'delayed') {
        // 弹出选择延后时长
        const choice = prompt('延后多久？\n输入分钟数（10 / 30 / 60）', '30');
        const n = parseInt(choice);
        if (!n || n <= 0) return;
        delayMinutes = n;
    }

    const data = {
        status: action,
        actual_time: time,
        delay_minutes: delayMinutes,
    };

    try {
        await api(`/api/records/${recordId}/action`, {
            method: 'POST',
            body: JSON.stringify(data),
        });

        const labels = { taken: '已服用', delayed: '已延后', skipped: '已跳过' };
        showToast(`记录成功：${labels[action]}`);

        // 刷新当前页面
        setTimeout(() => location.reload(), 500);
    } catch (e) {}
}

// ====== 提醒设置 ======
async function toggleReminder(reminderId, isActive) {
    try {
        await api(`/api/reminders/${reminderId}`, {
            method: 'PUT',
            body: JSON.stringify({ is_active: isActive }),
        });
    } catch (e) {
        // 恢复开关状态
        const toggle = document.querySelector(`[data-reminder-id="${reminderId}"]`);
        if (toggle) toggle.checked = !isActive;
    }
}

// ====== 药品搜索/过滤 ======
function filterMedicines(query) {
    const cards = document.querySelectorAll('.medicine-card');
    const lower = query.toLowerCase();
    cards.forEach(card => {
        const name = card.querySelector('.med-name')?.textContent?.toLowerCase() || '';
        card.style.display = name.includes(lower) ? '' : 'none';
    });
}

// ====== 历史记录加载 ======
async function loadHistory(dateStr) {
    const container = document.getElementById('historyContainer');
    if (!container) return;

    container.innerHTML = '<div class="loading show"><div class="spinner"></div><p>加载中...</p></div>';

    try {
        const url = dateStr ? `/api/records?date=${dateStr}` : '/api/records';
        const records = await api(url);

        if (!records || records.length === 0) {
            container.innerHTML = '<div class="empty-state"><div class="empty-icon">📋</div><div class="empty-text">暂无服药记录</div></div>';
            return;
        }

        container.innerHTML = records.map(r => {
            const iconMap = { taken: '✅', delayed: '⏰', skipped: '⏭️', pending: '⏳' };
            const labelMap = { taken: '已服用', delayed: '延后', skipped: '跳过', pending: '待服药' };
            return `
            <div class="history-item">
                <div class="status-icon ${r.status}">${iconMap[r.status] || '❓'}</div>
                <div class="hist-content">
                    <div class="hist-name">${r.medicine_name}</div>
                    <div class="hist-time">${r.scheduled_date} ${r.scheduled_time} · ${labelMap[r.status] || r.status}</div>
                </div>
                <div class="status-badge ${r.status}">${labelMap[r.status] || r.status}</div>
            </div>`;
        }).join('');
    } catch (e) {
        container.innerHTML = '<div class="empty-state"><div class="empty-text">加载失败</div></div>';
    }
}

// ====== 日期选择器 ======
function setupDatePicker() {
    const picker = document.getElementById('datePicker');
    if (!picker) return;

    const today = new Date().toISOString().split('T')[0];
    picker.value = today;
    picker.max = today;

    picker.addEventListener('change', () => loadHistory(picker.value));
}

// ====== Tab切换 ======
function setupTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tabGroup = btn.closest('.tabs');
            tabGroup.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        });
    });
}

// ====== 提醒: 创建提醒表单 ======
async function createReminder(e) {
    e.preventDefault();
    const form = e.target;
    const btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;

    const medicineId = document.getElementById('reminder_medicine_id').value;
    const data = {
        medicine_id: medicineId,
        remind_time: document.getElementById('reminder_time').value,
        frequency: document.getElementById('reminder_frequency').value,
        dosage: document.getElementById('reminder_dosage').value || '1片',
        days_of_week: document.getElementById('reminder_days').value || '',
    };

    try {
        await api('/api/reminders', {
            method: 'POST',
            body: JSON.stringify(data),
        });
        showToast('提醒设置成功！');
        setTimeout(() => location.reload(), 800);
    } catch (e) {
        btn.disabled = false;
    }
}

// ====== 删除药品 ======
async function deleteMedicine(medicineId) {
    if (!confirm('确定要删除这个药品吗？相关的提醒和记录也会被删除。')) return;

    try {
        await api(`/api/medicines/${medicineId}`, { method: 'DELETE' });
        showToast('药品已删除');
        setTimeout(() => location.reload(), 500);
    } catch (e) {}
}

// ====== 删除提醒 ======
async function deleteReminder(reminderId) {
    if (!confirm('确定要删除这个提醒吗？')) return;

    try {
        await api(`/api/reminders/${reminderId}`, { method: 'DELETE' });
        showToast('提醒已删除');
        setTimeout(() => location.reload(), 500);
    } catch (e) {}
}

// ====== 通知权限 ======
function requestNotificationPermission() {
    if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission();
    }
}

// ====== Web Push 自动订阅 ======
async function autoSubscribePush() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;
    try {
        const registration = await navigator.serviceWorker.ready;
        const existingSubscription = await registration.pushManager.getSubscription();
        if (existingSubscription) return; // 已订阅

        const permission = await Notification.requestPermission();
        if (permission !== 'granted') return;

        const vapidResp = await fetch('/api/push/vapid-public-key');
        if (!vapidResp.ok) return;
        const vapidData = await vapidResp.json();

        const subscription = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(vapidData.publicKey),
        });

        const subData = subscription.toJSON();
        await fetch('/api/push/subscribe', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                endpoint: subData.endpoint,
                keys: subData.keys,
            }),
        });
        console.log('Push notification subscribed');
    } catch (e) {
        console.log('Push subscription not available:', e.message);
    }
}

function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
}

// 定时检查提醒 (每分钟，作为服务端推送的补充)
function startNotificationChecker() {
    setInterval(async () => {
        try {
            const res = await fetch('/api/records/today');
            if (res.status === 401) return;

            const records = await res.json();
            const now = new Date();
            const currentTime = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;

            records.forEach(r => {
                if (r.status === 'pending' && r.scheduled_time === currentTime) {
                    if ('Notification' in window && Notification.permission === 'granted') {
                        new Notification('💊 服药提醒', {
                            body: `该服用 ${r.medicine_name} ${r.medicine_spec} 了`,
                            icon: '/static/images/icon-192.png',
                            tag: r.id,
                        });
                    }
                    showToast(`⏰ 该服用 ${r.medicine_name} 了`, 'info');
                }
            });
        } catch (e) {}
    }, 60000);
}

// ====== PWA 安装 ======
let deferredPrompt = null;

window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    const banner = document.getElementById('installBanner');
    if (banner) banner.style.display = 'flex';
});

window.addEventListener('appinstalled', () => {
    deferredPrompt = null;
    const banner = document.getElementById('installBanner');
    if (banner) banner.style.display = 'none';
    console.log('PWA installed successfully');
});

function installPWA() {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    deferredPrompt.userChoice.then(() => {
        deferredPrompt = null;
        const banner = document.getElementById('installBanner');
        if (banner) banner.style.display = 'none';
    });
}

function dismissInstall() {
    deferredPrompt = null;
    const banner = document.getElementById('installBanner');
    if (banner) banner.style.display = 'none';
}

// 已在 PWA 模式运行则隐藏安装提示
if (window.matchMedia('(display-mode: standalone)').matches || navigator.standalone) {
    document.addEventListener('DOMContentLoaded', () => {
        const banner = document.getElementById('installBanner');
        if (banner) banner.style.display = 'none';
    });
}

// ====== 初始化 ======
document.addEventListener('DOMContentLoaded', () => {
    setupUpload();
    setupTabs();
    setupDatePicker();
    // 不再自动弹出通知权限，改为用户主动点击设置页「开启推送」时申请
    // requestNotificationPermission();
    // 也不在加载时自动订阅推送
    // autoSubscribePush();
    startNotificationChecker();

    // 绑定表单事件
    const loginForm = document.getElementById('loginForm');
    if (loginForm) loginForm.addEventListener('submit', handleLogin);

    const registerForm = document.getElementById('registerForm');
    if (registerForm) registerForm.addEventListener('submit', handleRegister);

    const confirmForm = document.getElementById('confirmForm');
    if (confirmForm) confirmForm.addEventListener('submit', confirmMedicine);

    const manualForm = document.getElementById('manualForm');
    if (manualForm) manualForm.addEventListener('submit', handleManualAdd);

    const reminderForm = document.getElementById('reminderForm');
    if (reminderForm) reminderForm.addEventListener('submit', createReminder);

    const searchInput = document.getElementById('searchMedicines');
    if (searchInput) searchInput.addEventListener('input', (e) => filterMedicines(e.target.value));

    // 加载历史
    if (document.getElementById('historyContainer')) {
        loadHistory();
    }
});

// ====== Service Worker 注册 ======
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/js/sw.js').catch(() => {});
}
