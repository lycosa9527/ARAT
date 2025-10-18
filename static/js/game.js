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
        const response = await fetch(`/api${endpoint}`, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'API call failed');
        }
        
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        showNotification(error.message || 'Network error occurred');
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

// 显示正确答案并继续下一题
async function showCorrectAnswerAndContinue(isCorrect = false, correctAnswer) {
    console.log('[showCorrectAnswerAndContinue] Called with:', {
        isCorrect,
        correctAnswer,
        puzzle_id: gameState.currentPuzzle?.puzzle_id,
        currentPuzzle: gameState.currentPuzzle
    });
    
    const answerInput = document.getElementById('answerInput');
    const answerInput2 = document.getElementById('answerInput2');
    const answerBoxes = document.querySelectorAll('.answer-box');
    
    // 如果没有传入正确答案，尝试从API获取
    if (!correctAnswer) {
        console.warn('[showCorrectAnswerAndContinue] No correctAnswer provided, fetching from API...');
        try {
            const result = await apiCall('/game/get_answer', {
                method: 'POST',
                body: JSON.stringify({
                    puzzle_id: gameState.currentPuzzle?.puzzle_id
                })
            });
            console.log('[showCorrectAnswerAndContinue] API response:', result);
            correctAnswer = result.answer;
            console.log('[showCorrectAnswerAndContinue] Extracted answer:', correctAnswer);
        } catch (error) {
            console.error('[showCorrectAnswerAndContinue] Failed to get correct answer from API:', error);
            correctAnswer = '?'; // 后备方案
        }
    }
    
    if (!correctAnswer || correctAnswer === '?') {
        console.error('[showCorrectAnswerAndContinue] CRITICAL: Failed to retrieve correct answer!', {
            puzzle_id: gameState.currentPuzzle?.puzzle_id,
            correctAnswer,
            currentPuzzle: gameState.currentPuzzle
        });
    } else {
        console.log('[showCorrectAnswerAndContinue] Using correct answer:', correctAnswer);
    }
    
    // 禁用提交和跳过按钮
    const submitBtn = document.getElementById('submitAnswerBtn');
    const skipBtn = document.getElementById('skipBtn');
    const finishBtn = document.getElementById('finishBtn');
    if (submitBtn) submitBtn.disabled = true;
    if (skipBtn) skipBtn.disabled = true;
    if (finishBtn) finishBtn.disabled = true;
    
    // 在输入框显示正确答案
    if (answerInput) {
        answerInput.value = correctAnswer;
        answerInput.disabled = true;
    }
    if (answerInput2) {
        answerInput2.value = correctAnswer;
        answerInput2.disabled = true;
    }
    
    // 添加正确答案的样式
    answerBoxes.forEach(box => {
        box.classList.remove('incorrect');
        box.classList.add('correct');
    });
    
    // 2秒后继续下一题
    setTimeout(() => {
        // 重新启用按钮
        if (submitBtn) submitBtn.disabled = false;
        if (skipBtn) skipBtn.disabled = false;
        if (finishBtn) finishBtn.disabled = false;
        
        // 重新启用输入
        if (answerInput) answerInput.disabled = false;
        if (answerInput2) answerInput2.disabled = false;
        
        // 获取下一题
        getNextPuzzle();
    }, 2000);
}

async function submitAnswer() {
    const answerInput = document.getElementById('answerInput');
    if (!answerInput) {
        showNotification('请先加载题目');
        return;
    }
    
    const userAnswer = answerInput.value.trim();
    
    if (!userAnswer) {
        showNotification('请输入答案');
        return;
    }
    
    try {
        console.log('[submitAnswer] Validating answer:', {
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
        
        console.log('[submitAnswer] Validation API response:', result);
        
        const answerBox = document.querySelector('.answer-box');
        
        // 获取正确答案 - 确保有值
        const correctAnswer = result.correct_answer || result.answer;
        
        console.log('[submitAnswer] Extracted correct answer:', {
            correctAnswer,
            from_correct_answer_field: result.correct_answer,
            from_answer_field: result.answer,
            result_correct: result.correct
        });
        
        if (!correctAnswer) {
            console.warn('[submitAnswer] WARNING: Validation response missing correct_answer field!', result);
        }
        
        if (result.correct) {
            console.log('[submitAnswer] Answer is CORRECT!');
            // 答案正确
            const answerBoxes = document.querySelectorAll('.answer-box');
            answerBoxes.forEach(box => box.classList.add('correct'));
            gameState.correctCount++;
            gameState.score += 2;
            
            updateGameStats();
            showNotification(t('correct-answer'));
            
            // 显示正确答案2秒后继续
            console.log('[submitAnswer] Calling showCorrectAnswerAndContinue with correctAnswer:', correctAnswer);
            showCorrectAnswerAndContinue(true, correctAnswer);
            
        } else {
            console.log('[submitAnswer] Answer is INCORRECT');
            // 答案错误 - 显示错误提示，然后显示正确答案
            const answerBoxes = document.querySelectorAll('.answer-box');
            answerBoxes.forEach(box => box.classList.add('incorrect'));
            
            // 500ms后显示正确答案
            console.log('[submitAnswer] Will show correct answer after 500ms:', correctAnswer);
            setTimeout(() => {
                showCorrectAnswerAndContinue(false, correctAnswer);
            }, 500);
        }
        
    } catch (error) {
        console.error('Failed to validate answer:', error);
        showNotification('验证答案失败，请重试');
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
    stopTimer();
    gameState.isPlaying = false;
    
    // 清理会话
    try {
        await apiCall('/game/clear_session', {
            method: 'POST',
            body: JSON.stringify({
                session_id: gameState.sessionId
            })
        });
    } catch (error) {
        console.error('Failed to clear session:', error);
    }
    
    // 显示验证码模态框
    showCaptchaModal();
}

// ============================================================================
// 验证码和成绩提交
// ============================================================================

async function showCaptchaModal() {
    // 加载保存的用户信息
    const savedNickname = localStorage.getItem('playerNickname') || '';
    const savedSchool = localStorage.getItem('playerSchool') || '';
    
    document.getElementById('playerNickname').value = savedNickname;
    document.getElementById('playerSchool').value = savedSchool;
    
    // 生成验证码
    await refreshCaptcha();
    
    // 显示模态框
    document.getElementById('captchaModal').classList.add('show');
    
    // 设置焦点
    if (savedNickname) {
        document.getElementById('captchaInput').focus();
    } else {
        document.getElementById('playerNickname').focus();
    }
}

async function refreshCaptcha() {
    try {
        const data = await apiCall('/captcha/generate');
        gameState.captchaId = data.captcha_id;
        document.getElementById('captchaImage').src = data.image;
    } catch (error) {
        console.error('Failed to load captcha:', error);
        showNotification('验证码加载失败');
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
// 通知模态框
// ============================================================================

function showNotification(message) {
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
        console.log('[skipBtn] Skip button clicked', {
            isPlaying: gameState.isPlaying,
            currentPuzzle: gameState.currentPuzzle,
            puzzle_id: gameState.currentPuzzle?.puzzle_id
        });
        
        if (gameState.isPlaying && gameState.currentPuzzle) {
            // 获取正确答案然后显示
            try {
                console.log('[skipBtn] Fetching answer from API for puzzle:', gameState.currentPuzzle.puzzle_id);
                const result = await apiCall('/game/get_answer', {
                    method: 'POST',
                    body: JSON.stringify({
                        puzzle_id: gameState.currentPuzzle.puzzle_id
                    })
                });
                
                console.log('[skipBtn] API response:', result);
                console.log('[skipBtn] Extracted answer:', result.answer);
                
                // 直接传递答案显示
                console.log('[skipBtn] Calling showCorrectAnswerAndContinue with answer:', result.answer);
                showCorrectAnswerAndContinue(false, result.answer);
            } catch (error) {
                console.error('[skipBtn] Failed to get answer:', error);
                // 即使失败也继续下一题
                getNextPuzzle();
            }
        } else {
            console.warn('[skipBtn] Skip button clicked but game not ready:', {
                isPlaying: gameState.isPlaying,
                hasPuzzle: !!gameState.currentPuzzle
            });
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

