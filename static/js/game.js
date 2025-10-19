/**
 * ARAT 游戏逻辑
 * 
 * 功能:
 * - 游戏会话管理 (Session Management)
 * - Catapult预生成机制
 * - 答案验证 (精确匹配 + LLM验证)
 * - localStorage持久化用户信息
 * - 双语支持
 * 
 * Author: lyc9527
 * Team: MTEL Team from Educational Technology, Beijing Normal University
 */

// ============================================================================
// 全局状态
// ============================================================================

const gameState = {
    sessionId: null,
    currentPuzzle: null,
    difficulty: 'easy',
    language: 'zh',
    score: 0,
    correctCount: 0,
    timeRemaining: 300, // 5 minutes
    timerInterval: null,
    isPlaying: false,
    captchaId: null,
    history: [] // 题目历史记录
};

// ============================================================================
// API 调用函数
// ============================================================================

async function apiCall(endpoint, options = {}) {
    try {
        console.log(`[apiCall] ${options.method || 'GET'} ${endpoint}`, options.body ? JSON.parse(options.body) : '');
        
        const response = await fetch(`/api${endpoint}`, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        });
        
        if (!response.ok) {
            const error = await response.json();
            console.error(`[apiCall] Error response from ${endpoint}:`, error);
            throw new Error(error.detail || 'API call failed');
        }
        
        const data = await response.json();
        console.log(`[apiCall] Success response from ${endpoint}:`, data);
        return data;
    } catch (error) {
        console.error(`[apiCall] Failed ${endpoint}:`, error);
        // Don't automatically show notification - let caller handle it
        throw error;
    }
}

// ============================================================================
// 游戏会话管理
// ============================================================================

async function startGameSession() {
    // 生成会话ID
    gameState.sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    gameState.difficulty = document.getElementById('difficultySelect').value;
    
    console.log('[startGameSession] Starting new game session:', {
        sessionId: gameState.sessionId,
        difficulty: gameState.difficulty,
        language: gameState.language
    });
    
    // Show loading state
    const startBtn = document.getElementById('startGameBtn');
    const originalText = startBtn.innerHTML;
    startBtn.disabled = true;
    startBtn.innerHTML = `<span>${t('loading-puzzle')}</span>`;
    startBtn.style.opacity = '0.7';
    startBtn.style.cursor = 'wait';
    
    try {
        const result = await apiCall('/game/start_session', {
            method: 'POST',
            body: JSON.stringify({
                session_id: gameState.sessionId,
                difficulty: gameState.difficulty,
                language: gameState.language,
                llm: 'qwen'
            })
        });
        
        console.log('[startGameSession] Session started, received:', result);
        
        // 获取第一题
        gameState.currentPuzzle = result.first_puzzle;
        gameState.history.push(gameState.currentPuzzle);
        
        console.log('[startGameSession] First puzzle:', {
            puzzle: gameState.currentPuzzle,
            hasAnswer: 'answer' in gameState.currentPuzzle,
            answerValue: gameState.currentPuzzle?.answer,
            puzzle_id: gameState.currentPuzzle?.puzzle_id
        });
        
        // 显示题目
        displayPuzzle(gameState.currentPuzzle);
        
        // 开始计时
        startTimer();
        
        // 显示游戏UI
        document.getElementById('landingPage').style.display = 'none';
        document.getElementById('gameUI').style.display = 'block';
        
        gameState.isPlaying = true;
        
    } catch (error) {
        console.error('Failed to start game:', error);
        showNotification('游戏启动失败，请重试');
        
        // Reset button state on error
        startBtn.disabled = false;
        startBtn.innerHTML = originalText;
        startBtn.style.opacity = '1';
        startBtn.style.cursor = 'pointer';
    }
}

async function getNextPuzzle() {
    try {
        console.log('[getNextPuzzle] Requesting next puzzle for session:', gameState.sessionId);
        
        const puzzle = await apiCall('/game/next_puzzle', {
            method: 'POST',
            body: JSON.stringify({
                session_id: gameState.sessionId
            })
        });
        
        console.log('[getNextPuzzle] Received puzzle:', {
            puzzle,
            hasAnswer: 'answer' in puzzle,
            answerValue: puzzle.answer,
            puzzle_id: puzzle.puzzle_id
        });
        
        gameState.currentPuzzle = puzzle;
        gameState.history.push(puzzle);
        
        displayPuzzle(puzzle);
        
        // 清空输入
        document.getElementById('answerInput').value = '';
        
    } catch (error) {
        console.error('[getNextPuzzle] Failed to get next puzzle:', error);
        showNotification('获取题目失败，请重试');
    }
}

window.displayPuzzle = function displayPuzzle(puzzle) {
    console.log('[displayPuzzle] Displaying puzzle:', {
        puzzle,
        hasAnswer: 'answer' in puzzle,
        answerValue: puzzle.answer,
        puzzle_id: puzzle.puzzle_id,
        language: gameState.language
    });
    
    if (gameState.language === 'zh') {
        // 中文模式 (2+1): A | B | Answer (answer always on the right)
        const puzzleBoxes = document.getElementById('puzzleBoxes');
        
        puzzleBoxes.innerHTML = `
            <div class="word-box" id="char1">${puzzle.char1}</div>
            <div class="word-box divider-box">
                <span style="font-size: 2rem; color: var(--text-light);">|</span>
            </div>
            <div class="word-box" id="char2">${puzzle.char2}</div>
            <div class="word-box divider-box">
                <span style="font-size: 2rem; color: var(--text-light);">|</span>
            </div>
            <div class="word-box answer-box">
                <input type="text" id="answerInput" maxlength="10" placeholder="?" />
            </div>
        `;
        
        // Focus answer input
        setTimeout(() => {
            const answerInput = document.querySelector('#answerInput');
            if (answerInput) {
                answerInput.focus();
            }
        }, 100);
    } else {
        // 英文模式 (3+1) - 需要调整HTML结构
        // 这里简化处理，实际应该动态创建3个word box
        document.getElementById('char1').textContent = puzzle.word1;
        document.getElementById('char2').textContent = puzzle.word3;
        document.getElementById('answerInput').placeholder = '?';
        document.getElementById('answerInput').maxLength = 20;
    }
    
    // 重置样式
    const answerBoxes = document.querySelectorAll('.answer-box');
    answerBoxes.forEach(box => {
        box.classList.remove('correct', 'incorrect');
    });
    
    // Demo mode: Show the answer
    if (window.isDemoMode && document.getElementById('correctAnswerText')) {
        document.getElementById('correctAnswerText').textContent = puzzle.answer || '?';
    }
}

// ============================================================================
// 答案验证
// ============================================================================

// 显示正确答案并继续下一题 (优化版 - 预取下一题)
async function showCorrectAnswerAndContinue(isCorrect = false, correctAnswer) {
    console.log('[showCorrectAnswerAndContinue] ========== FUNCTION CALLED ==========');
    console.log('[showCorrectAnswerAndContinue] Parameters:', {
        isCorrect,
        correctAnswer,
        puzzle_id: gameState.currentPuzzle?.puzzle_id
    });
    
    const answerInput = document.getElementById('answerInput');
    const answerInput2 = document.getElementById('answerInput2');
    const answerBoxes = document.querySelectorAll('.answer-box');
    
    // 如果没有传入正确答案，尝试从API获取
    if (!correctAnswer) {
        console.warn('[showCorrectAnswerAndContinue] No answer provided, fetching from API...');
        try {
            const result = await apiCall('/game/get_answer', {
                method: 'POST',
                body: JSON.stringify({
                    puzzle_id: gameState.currentPuzzle?.puzzle_id
                })
            });
            correctAnswer = result.answer;
            console.log('[showCorrectAnswerAndContinue] Answer fetched:', correctAnswer);
        } catch (error) {
            console.error('[showCorrectAnswerAndContinue] Failed to get answer:', error);
            correctAnswer = '?';
        }
    }
    
    if (!correctAnswer || correctAnswer === '?') {
        console.error('[showCorrectAnswerAndContinue] CRITICAL: No valid answer!');
    }
    
    // ===================================================================
    // STEP 1: Start prefetching the NEXT puzzle (background, non-blocking)
    // ===================================================================
    console.log('[showCorrectAnswerAndContinue] Step 1: Starting to prefetch NEXT puzzle in background...');
    let nextPuzzlePromise = apiCall('/game/next_puzzle', {
        method: 'POST',
        body: JSON.stringify({
            session_id: gameState.sessionId
        })
    });
    console.log('[showCorrectAnswerAndContinue] ✓ Next puzzle fetch initiated (async)');
    
    // ===================================================================
    // STEP 2: Display the answer in current puzzle (user feedback)
    // ===================================================================
    console.log('[showCorrectAnswerAndContinue] Step 2: Displaying answer in current puzzle');
    
    // Disable buttons
    const submitBtn = document.getElementById('submitAnswerBtn');
    const skipBtn = document.getElementById('skipBtn');
    const finishBtn = document.getElementById('finishBtn');
    if (submitBtn) submitBtn.disabled = true;
    if (skipBtn) skipBtn.disabled = true;
    if (finishBtn) finishBtn.disabled = true;
    
    // Show answer in input
    if (answerInput) {
        answerInput.value = correctAnswer;
        answerInput.disabled = true;
        console.log('[showCorrectAnswerAndContinue] ✓ Answer displayed:', answerInput.value);
    }
    if (answerInput2) {
        answerInput2.value = correctAnswer;
        answerInput2.disabled = true;
    }
    
    // Add visual feedback (green box)
    answerBoxes.forEach(box => {
        box.classList.remove('incorrect');
        box.classList.add('correct');
    });
    
    console.log('[showCorrectAnswerAndContinue] ✓ Answer is NOW visible for 2.5 seconds');
    
    // ===================================================================
    // STEP 3: Wait 2.5 seconds, then load the prefetched puzzle
    // ===================================================================
    setTimeout(async () => {
        console.log('[showCorrectAnswerAndContinue] Step 3: Timeout expired, loading next puzzle...');
        
        try {
            // Wait for the prefetched puzzle (should already be ready)
            const puzzle = await nextPuzzlePromise;
            console.log('[showCorrectAnswerAndContinue] ✓ Next puzzle ready:', puzzle.puzzle_id);
            
            // Update game state
            gameState.currentPuzzle = puzzle;
            gameState.history.push(puzzle);
            
            // Re-enable controls
            if (submitBtn) submitBtn.disabled = false;
            if (skipBtn) skipBtn.disabled = false;
            if (finishBtn) finishBtn.disabled = false;
            
            // Display the new puzzle (this will recreate the HTML)
            displayPuzzle(puzzle);
            
            console.log('[showCorrectAnswerAndContinue] ========== COMPLETE ==========');
            
        } catch (error) {
            console.error('[showCorrectAnswerAndContinue] Error loading next puzzle:', error);
            showInlineNotification('获取下一题失败', 'error');
            
            // Re-enable controls on error
            if (submitBtn) submitBtn.disabled = false;
            if (skipBtn) skipBtn.disabled = false;
            if (finishBtn) finishBtn.disabled = false;
        }
    }, 2500); // 2.5 seconds - enough time to see the answer
}

async function submitAnswer() {
    console.log('[submitAnswer] ========== SUBMIT BUTTON CLICKED ==========');
    
    const answerInput = document.getElementById('answerInput');
    if (!answerInput) {
        console.error('[submitAnswer] Answer input not found!');
        showInlineNotification('请先加载题目', 'error');
        return;
    }
    
    const userAnswer = answerInput.value.trim();
    
    if (!userAnswer) {
        console.warn('[submitAnswer] Empty answer submitted');
        showInlineNotification('请输入答案', 'error');
        return;
    }
    
    try {
        console.log('[submitAnswer] Step 1: Validating answer:', {
            puzzle_id: gameState.currentPuzzle.puzzle_id,
            userAnswer,
            currentPuzzle: gameState.currentPuzzle
        });
        
        const result = await apiCall('/game/validate', {
            method: 'POST',
            body: JSON.stringify({
                puzzle_id: gameState.currentPuzzle.puzzle_id,
                answer: userAnswer,
                llm: 'qwen'
            })
        });
        
        console.log('[submitAnswer] Step 2: Validation API response:', result);
        
        const answerBox = document.querySelector('.answer-box');
        
        // 获取正确答案 - 确保有值
        const correctAnswer = result.correct_answer || result.answer;
        
        console.log('[submitAnswer] Step 3: Extracted correct answer:', {
            correctAnswer,
            from_correct_answer_field: result.correct_answer,
            from_answer_field: result.answer,
            result_correct: result.correct
        });
        
        if (!correctAnswer) {
            console.error('[submitAnswer] CRITICAL: Validation response missing correct_answer field!', result);
        }
        
        if (result.correct) {
            console.log('[submitAnswer] Step 4a: Answer is CORRECT! ✓');
            // 答案正确
            const answerBoxes = document.querySelectorAll('.answer-box');
            answerBoxes.forEach(box => box.classList.add('correct'));
            gameState.correctCount++;
            gameState.score += 2;
            
            updateGameStats();
            showInlineNotification(t('correct-answer'), 'success');
            
            // 显示正确答案2秒后继续
            console.log('[submitAnswer] Step 5: Calling showCorrectAnswerAndContinue with correctAnswer:', correctAnswer);
            showCorrectAnswerAndContinue(true, correctAnswer);
            
        } else {
            console.log('[submitAnswer] Step 4b: Answer is INCORRECT ✗');
            // 答案错误 - 显示错误提示，然后显示正确答案
            const answerBoxes = document.querySelectorAll('.answer-box');
            answerBoxes.forEach(box => box.classList.add('incorrect'));
            
            showInlineNotification(t('wrong-answer') || '答案错误', 'error');
            
            // 500ms后显示正确答案
            console.log('[submitAnswer] Step 5: Will show correct answer after 500ms:', correctAnswer);
            setTimeout(() => {
                console.log('[submitAnswer] Step 6: Timeout expired, calling showCorrectAnswerAndContinue');
                showCorrectAnswerAndContinue(false, correctAnswer);
            }, 500);
        }
        
        console.log('[submitAnswer] ========== SUBMIT FLOW COMPLETE ==========');
        
    } catch (error) {
        console.error('[submitAnswer] ========== ERROR IN SUBMIT FLOW ==========');
        console.error('[submitAnswer] Error details:', error);
        console.error('[submitAnswer] Error stack:', error.stack);
        showInlineNotification('验证答案失败，请重试', 'error');
    }
}

function updateGameStats() {
    document.getElementById('scoreDisplay').textContent = gameState.score;
    document.getElementById('correctDisplay').textContent = gameState.correctCount;
}

// ============================================================================
// 计时器
// ============================================================================

function startTimer() {
    gameState.timeRemaining = 300; // 5 minutes
    
    gameState.timerInterval = setInterval(() => {
        gameState.timeRemaining--;
        
        const minutes = Math.floor(gameState.timeRemaining / 60);
        const seconds = gameState.timeRemaining % 60;
        document.getElementById('timeDisplay').textContent = 
            `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        
        if (gameState.timeRemaining <= 0) {
            stopTimer(); // Stop timer FIRST to prevent repeated calls
            endGame();
        }
    }, 1000);
}

function stopTimer() {
    if (gameState.timerInterval) {
        clearInterval(gameState.timerInterval);
        gameState.timerInterval = null;
    }
}

// ============================================================================
// 游戏结束
// ============================================================================

async function endGame() {
    console.log('[endGame] ========== GAME ENDING ==========');
    
    // Prevent multiple calls
    if (!gameState.isPlaying) {
        console.log('[endGame] Already ended, ignoring duplicate call');
        return;
    }
    
    stopTimer();
    gameState.isPlaying = false;
    
    console.log('[endGame] Clearing session:', gameState.sessionId);
    
    // 清理会话
    try {
        await apiCall('/game/clear_session', {
            method: 'POST',
            body: JSON.stringify({
                session_id: gameState.sessionId
            })
        });
        console.log('[endGame] Session cleared successfully');
    } catch (error) {
        console.error('[endGame] Failed to clear session:', error);
    }
    
    // 显示验证码模态框
    console.log('[endGame] Showing captcha modal');
    showCaptchaModal();
    
    console.log('[endGame] ========== GAME END COMPLETE ==========');
}

// ============================================================================
// 验证码和成绩提交
// ============================================================================

async function showCaptchaModal() {
    console.log('[showCaptchaModal] Opening captcha modal');
    
    // 加载保存的用户信息
    const savedNickname = localStorage.getItem('playerNickname') || '';
    const savedSchool = localStorage.getItem('playerSchool') || '';
    
    document.getElementById('playerNickname').value = savedNickname;
    document.getElementById('playerSchool').value = savedSchool;
    
    // 生成验证码
    console.log('[showCaptchaModal] Generating captcha...');
    await refreshCaptcha();
    
    // 显示模态框
    document.getElementById('captchaModal').classList.add('show');
    
    // 设置焦点
    if (savedNickname) {
        document.getElementById('captchaInput').focus();
    } else {
        document.getElementById('playerNickname').focus();
    }
    
    console.log('[showCaptchaModal] Modal shown successfully');
}

async function refreshCaptcha() {
    console.log('[refreshCaptcha] Requesting new captcha...');
    try {
        const data = await apiCall('/captcha/generate');
        gameState.captchaId = data.captcha_id;
        document.getElementById('captchaImage').src = data.image;
        console.log('[refreshCaptcha] Captcha loaded successfully:', data.captcha_id);
    } catch (error) {
        console.error('[refreshCaptcha] Failed to load captcha:', error);
        showInlineNotification('验证码加载失败，请点击刷新按钮重试', 'error');
    }
}

async function submitScore(event) {
    event.preventDefault();
    
    const nickname = document.getElementById('playerNickname').value.trim();
    const school = document.getElementById('playerSchool').value.trim();
    const captcha = document.getElementById('captchaInput').value.trim();
    
    if (!nickname) {
        showNotification('请输入昵称');
        return;
    }
    
    if (!captcha || captcha.length !== 4) {
        showNotification('请输入4位验证码');
        return;
    }
    
    try {
        const result = await apiCall('/game/submit_score', {
            method: 'POST',
            body: JSON.stringify({
                captcha_id: gameState.captchaId,
                captcha: captcha,
                nickname: nickname,
                school: school || null,
                session_id: gameState.sessionId,
                correct_count: gameState.correctCount,
                total_score: gameState.score,
                total_time: 300 - gameState.timeRemaining,
                difficulty: gameState.difficulty,
                language: gameState.language
            })
        });
        
        // 保存用户信息到localStorage
        localStorage.setItem('playerNickname', nickname);
        localStorage.setItem('playerSchool', school);
        
        // 关闭模态框
        document.getElementById('captchaModal').classList.remove('show');
        
        // 显示成绩
        showNotification(`${t('game-over')} ${t('your-score')} ${gameState.score}\n排名: ${result.rank}`);
        
        // 重置游戏
        resetGame();
        
    } catch (error) {
        console.error('Failed to submit score:', error);
        showNotification('成绩提交失败：' + error.message);
        // 刷新验证码
        refreshCaptcha();
        document.getElementById('captchaInput').value = '';
    }
}

// ============================================================================
// 通知系统
// ============================================================================

// 显示内联通知（在提示文字下方的通知区域）
function showInlineNotification(message, type = 'info') {
    console.log(`[showInlineNotification] ${type.toUpperCase()}: ${message}`);
    
    // Get notification area (below hint text)
    const notifArea = document.getElementById('notificationArea');
    if (!notifArea) {
        console.warn('[showInlineNotification] Notification area not found, falling back to body');
        return;
    }
    
    // Remove existing notification
    const existingNotif = notifArea.querySelector('.inline-notification');
    if (existingNotif) {
        existingNotif.remove();
    }
    
    // Create notification element
    const notif = document.createElement('div');
    notif.className = `inline-notification ${type}`;
    notif.textContent = message;
    notif.style.cssText = `
        background: ${type === 'error' ? '#ef4444' : type === 'success' ? '#10b981' : '#3b82f6'};
        color: white;
        padding: 12px 24px;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        font-size: 14px;
        font-weight: 500;
    `;
    
    // Append to notification area (not body)
    notifArea.appendChild(notif);
    
    // Auto-hide after 3 seconds
    setTimeout(() => {
        notif.style.opacity = '0';
        notif.style.transform = 'scale(0.9)';
        notif.style.transition = 'all 0.3s ease';
        setTimeout(() => notif.remove(), 300);
    }, 3000);
}

// 显示模态通知（用于重要信息）
function showNotification(message) {
    console.log(`[showNotification] MODAL: ${message}`);
    document.getElementById('notificationMessage').textContent = message;
    document.getElementById('notificationModal').classList.add('show');
}

function hideNotification() {
    document.getElementById('notificationModal').classList.remove('show');
}

// ============================================================================
// 游戏重置
// ============================================================================

function resetGame() {
    gameState.sessionId = null;
    gameState.currentPuzzle = null;
    gameState.score = 0;
    gameState.correctCount = 0;
    gameState.timeRemaining = 300;
    gameState.history = [];
    
    updateGameStats();
    
    document.getElementById('gameUI').style.display = 'none';
    document.getElementById('landingPage').style.display = 'block';
    
    // 清空所有输入框
    const answerInput = document.getElementById('answerInput');
    const answerInput2 = document.getElementById('answerInput2');
    if (answerInput) answerInput.value = '';
    if (answerInput2) answerInput2.value = '';
}

// ============================================================================
// 语言切换
// ============================================================================

function toggleLanguage() {
    if (gameState.isPlaying) {
        showNotification(t('difficulty-warning'));
        return;
    }
    
    if (gameState.language === 'zh') {
        gameState.language = 'en';
        currentLang = 'en';
        setLanguage('en');
        document.getElementById('languageToggle').textContent = 'EN';
    } else {
        gameState.language = 'zh';
        currentLang = 'zh';
        setLanguage('zh');
        document.getElementById('languageToggle').textContent = 'CN';
    }
}

// ============================================================================
// About & Share Modals
// ============================================================================

function showAboutModal() {
    document.getElementById('aboutModal').classList.add('show');
}

function hideAboutModal() {
    document.getElementById('aboutModal').classList.remove('show');
}

async function showShareModal() {
    // Get share URL from backend
    try {
        const response = await fetch('/api/config/share_url');
        const data = await response.json();
        const shareUrl = data.share_url || window.location.href;
        
        document.getElementById('shareLinkInput').value = shareUrl;
        document.getElementById('shareModal').classList.add('show');
        document.getElementById('shareSuccess').style.display = 'none';
    } catch (error) {
        // Fallback to current URL
        document.getElementById('shareLinkInput').value = window.location.href;
        document.getElementById('shareModal').classList.add('show');
        document.getElementById('shareSuccess').style.display = 'none';
    }
}

function hideShareModal() {
    document.getElementById('shareModal').classList.remove('show');
}

function copyShareLink() {
    const input = document.getElementById('shareLinkInput');
    input.select();
    input.setSelectionRange(0, 99999); // For mobile devices
    
    try {
        navigator.clipboard.writeText(input.value).then(() => {
            document.getElementById('shareSuccess').style.display = 'block';
            setTimeout(() => {
                document.getElementById('shareSuccess').style.display = 'none';
            }, 3000);
        }).catch(() => {
            // Fallback for older browsers
            document.execCommand('copy');
            document.getElementById('shareSuccess').style.display = 'block';
            setTimeout(() => {
                document.getElementById('shareSuccess').style.display = 'none';
            }, 3000);
        });
    } catch (err) {
        console.error('Failed to copy:', err);
    }
}

// ============================================================================
// 事件监听器
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    // 开始游戏
    document.getElementById('startGameBtn').addEventListener('click', startGameSession);
    
    // 提交答案
    document.getElementById('submitAnswerBtn').addEventListener('click', submitAnswer);
    
    // 回车提交答案
    document.getElementById('answerInput').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            submitAnswer();
        }
    });
    
    // 跳过按钮
    document.getElementById('skipBtn').addEventListener('click', async () => {
        console.log('[skipBtn] ========== SKIP BUTTON CLICKED ==========');
        console.log('[skipBtn] Step 1: Initial state check:', {
            isPlaying: gameState.isPlaying,
            currentPuzzle: gameState.currentPuzzle,
            puzzle_id: gameState.currentPuzzle?.puzzle_id
        });
        
        if (gameState.isPlaying && gameState.currentPuzzle) {
            // 获取正确答案然后显示
            try {
                console.log('[skipBtn] Step 2: Fetching answer from API for puzzle:', gameState.currentPuzzle.puzzle_id);
                const result = await apiCall('/game/get_answer', {
                    method: 'POST',
                    body: JSON.stringify({
                        puzzle_id: gameState.currentPuzzle.puzzle_id
                    })
                });
                
                console.log('[skipBtn] Step 3: API response received:', result);
                console.log('[skipBtn] Step 4: Extracted answer:', result.answer);
                
                if (!result.answer) {
                    console.error('[skipBtn] CRITICAL: No answer in API response!', result);
                }
                
                // 直接传递答案显示
                console.log('[skipBtn] Step 5: Calling showCorrectAnswerAndContinue with answer:', result.answer);
                showCorrectAnswerAndContinue(false, result.answer);
                
                console.log('[skipBtn] ========== SKIP FLOW COMPLETE ==========');
            } catch (error) {
                console.error('[skipBtn] ========== ERROR IN SKIP FLOW ==========');
                console.error('[skipBtn] Error details:', error);
                console.error('[skipBtn] Error stack:', error.stack);
                showInlineNotification('获取答案失败，跳到下一题', 'error');
                // 即使失败也继续下一题
                getNextPuzzle();
            }
        } else {
            console.warn('[skipBtn] Skip button clicked but game not ready:', {
                isPlaying: gameState.isPlaying,
                hasPuzzle: !!gameState.currentPuzzle
            });
            showInlineNotification('游戏未开始或题目未加载', 'error');
        }
    });
    
    // 结束游戏按钮
    document.getElementById('finishBtn').addEventListener('click', () => {
        if (gameState.isPlaying) {
            // 确认是否结束游戏
            if (confirm(t('confirm-finish') || '确定要结束游戏吗？')) {
                console.log('[finishBtn] User confirmed game finish');
                endGame();
            }
        } else {
            showInlineNotification('游戏未开始', 'error');
        }
    });
    
    // 语言切换
    document.getElementById('languageToggle').addEventListener('click', toggleLanguage);
    
    // 验证码刷新
    document.getElementById('refreshCaptcha').addEventListener('click', refreshCaptcha);
    
    // 成绩提交
    document.getElementById('captchaForm').addEventListener('submit', submitScore);
    
    // 通知确认
    document.getElementById('notificationOk').addEventListener('click', hideNotification);
    
    // 难度选择变化警告
    document.getElementById('difficultySelect').addEventListener('change', () => {
        if (gameState.isPlaying) {
            showNotification(t('difficulty-warning'));
            // 可以选择重置游戏或保持当前难度
        }
    });
    
    // About 按钮
    document.getElementById('aboutBtn').addEventListener('click', showAboutModal);
    document.getElementById('closeAboutModal').addEventListener('click', hideAboutModal);
    
    // Share 按钮
    document.getElementById('shareBtn').addEventListener('click', showShareModal);
    document.getElementById('closeShareModal').addEventListener('click', hideShareModal);
    document.getElementById('copyLinkBtn').addEventListener('click', copyShareLink);
    
    // 点击模态框背景关闭
    document.getElementById('aboutModal').addEventListener('click', (e) => {
        if (e.target.id === 'aboutModal') {
            hideAboutModal();
        }
    });
    
    document.getElementById('shareModal').addEventListener('click', (e) => {
        if (e.target.id === 'shareModal') {
            hideShareModal();
        }
    });
});

