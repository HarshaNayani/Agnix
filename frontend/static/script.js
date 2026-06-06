let token = localStorage.getItem("token");
let socket = null;
let currentChatId = null;

// Wait for DOM to fully load before running code
document.addEventListener("DOMContentLoaded", function() {
    console.log("DOM loaded, initializing...");
    
    // Check auto login
    if (token) {
        // Hide auth section, show main app
        const authSection = document.getElementById("authSection");
        const mainApp = document.getElementById("mainApp");
        
        if (authSection) authSection.style.display = "none";
        if (mainApp) mainApp.style.display = "flex";
        
        loadHistory();
        loadProfile();
    }
    
    // Setup send button event listener
    const sendBtn = document.getElementById("sendBtn");
    const messageInput = document.getElementById("messageInput");
    
    if (sendBtn) {
        // Remove any existing listeners by cloning and replacing
        const newSendBtn = sendBtn.cloneNode(true);
        sendBtn.parentNode.replaceChild(newSendBtn, sendBtn);
        
        newSendBtn.addEventListener("click", function() {
            console.log("Send button clicked");
            sendMessage();
        });
    }
    
    if (messageInput) {
        messageInput.addEventListener("keypress", function(event) {
            if (event.key === 'Enter') {
                console.log("Enter key pressed");
                event.preventDefault();
                sendMessage();
            }
        });
    }
});

// Tab switching
function showTab(tab) {
    const loginTab = document.getElementById("loginTab");
    const registerTab = document.getElementById("registerTab");
    const tabs = document.querySelectorAll(".tab-btn");
    
    if (!loginTab || !registerTab) return;
    
    if (tab === 'login') {
        loginTab.classList.add("active");
        registerTab.classList.remove("active");
        if (tabs[0]) tabs[0].classList.add("active");
        if (tabs[1]) tabs[1].classList.remove("active");
    } else {
        loginTab.classList.remove("active");
        registerTab.classList.add("active");
        if (tabs[0]) tabs[0].classList.remove("active");
        if (tabs[1]) tabs[1].classList.add("active");
    }
}

// Login
async function login() {
    const username = document.getElementById("loginUsername")?.value;
    const password = document.getElementById("loginPassword")?.value;

    if (!username || !password) {
        alert("Please enter username and password");
        return;
    }

    try {
        const res = await fetch("http://127.0.0.1:8000/login", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({username, password})
        });

        const data = await res.json();

        if (data.access_token) {
            localStorage.setItem("token", data.access_token);
            localStorage.setItem("username", username);
            location.reload();
        } else {
            alert("Login failed: " + (data.detail || "Unknown error"));
        }
    } catch (error) {
        alert("Login error: " + error.message);
    }
}

// Register
async function register() {
    const username = document.getElementById("regUsername")?.value;
    const email = document.getElementById("regEmail")?.value;
    const password = document.getElementById("regPassword")?.value;

    if (!username || !email || !password) {
        alert("Please fill all fields");
        return;
    }

    try {
        const res = await fetch("http://127.0.0.1:8000/register", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                username: username,
                password: password,
                email: email
            })
        });

        if (res.ok) {
            alert("Registration successful! Please login.");
            showTab('login');
            const loginUsername = document.getElementById("loginUsername");
            if (loginUsername) loginUsername.value = username;
        } else {
            const error = await res.json();
            alert("Registration failed: " + error.detail);
        }
    } catch (error) {
        alert("Registration error: " + error.message);
    }
}

// Load profile
function loadProfile() {
    const username = localStorage.getItem("username") || "User";
    const profileSpan = document.getElementById("profileUsername");
    if (profileSpan) profileSpan.innerText = username;
}

// Load chat history
async function loadHistory() {
    token = localStorage.getItem("token");
    if (!token) return;
    
    try {
        const res = await fetch("http://127.0.0.1:8000/chats/", {
            headers: {
                "Authorization": "Bearer " + token
            }
        });

        let chats = await res.json();
        const list = document.getElementById("historyList");

        if (!list) return;
        list.innerHTML = "";

        if (chats.length === 0) {
            await createNewChat();
            return;
        }

        chats.forEach(chat => {
            const li = document.createElement("li");
            li.innerHTML = `<i class="fas fa-comment"></i> ${chat.title || 'Chat ' + chat.id}`;
            li.onclick = () => loadChat(chat.id);
            list.appendChild(li);
        });

        // Load first chat
        if (chats.length > 0 && !currentChatId) {
            await loadChat(chats[0].id);
        }
    } catch (error) {
        console.error("Error loading history:", error);
    }
}

// Create new chat
async function createNewChat() {
    token = localStorage.getItem("token");
    if (!token) return;
    
    try {
        const res = await fetch("http://127.0.0.1:8000/chats/", {
            method: "POST",
            headers: {
                "Authorization": "Bearer " + token,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ title: "New Conversation" })
        });

        const newChat = await res.json();
        await loadChat(newChat.id);
        await loadHistory();
    } catch (error) {
        console.error("Error creating chat:", error);
    }
}

// Load specific chat
async function loadChat(chatId) {
    currentChatId = chatId;
    const chatTitle = document.getElementById("chatTitle");
    if (chatTitle) chatTitle.innerText = `Chat ${chatId}`;
    
    // Clear chat box
    const chatBox = document.getElementById("chatBox");
    if (chatBox) {
        chatBox.innerHTML = '<div class="welcome-message"><i class="fas fa-robot"></i><h3>Welcome to Agnix AI!</h3><p>How can I help you today?</p></div>';
    }
    
    // Connect WebSocket
    connectWebSocket();
    
    // Load messages from history
    try {
        const res = await fetch("http://127.0.0.1:8000/chats/", {
            headers: {
                "Authorization": "Bearer " + token
            }
        });
        const chats = await res.json();
        const currentChat = chats.find(c => c.id === chatId);
        
        if (currentChat && currentChat.messages && chatBox) {
            chatBox.innerHTML = "";
            currentChat.messages.forEach(msg => {
                addMessageToChat(msg.role, msg.content);
            });
        }
    } catch (error) {
        console.error("Error loading messages:", error);
    }
}

// Connect WebSocket
function connectWebSocket() {
    if (!currentChatId) {
        console.log("No chat ID, can't connect WebSocket");
        return;
    }
    
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.close();
    }

    console.log("Connecting WebSocket for chat:", currentChatId);
    socket = new WebSocket(`wss://agnix-backend.onrender.com/ws/${currentChatId}`);
    
    socket.onopen = function() {
        console.log("WebSocket connected successfully!");
        const sendBtn = document.getElementById("sendBtn");
        const messageInput = document.getElementById("messageInput");
        if (sendBtn) sendBtn.disabled = false;
        if (messageInput) messageInput.disabled = false;
    };

    socket.onmessage = function(event) {
        console.log("Message received:", event.data);
        const data = JSON.parse(event.data);
        addMessageToChat(data.role, data.content);
    };
    
    socket.onerror = function(error) {
        console.error("WebSocket error:", error);
        addMessageToChat("assistant", "⚠️ Connection error. Please refresh the page.");
    };
    
    socket.onclose = function() {
        console.log("WebSocket disconnected");
        const sendBtn = document.getElementById("sendBtn");
        const messageInput = document.getElementById("messageInput");
        if (sendBtn) sendBtn.disabled = true;
        if (messageInput) messageInput.disabled = true;
    };
}

// Add message to chat
function addMessageToChat(role, content) {
    const chatBox = document.getElementById("chatBox");
    if (!chatBox) return;
    
    // Remove welcome message if exists
    if (chatBox.children.length === 1 && chatBox.children[0].classList?.contains('welcome-message')) {
        chatBox.innerHTML = "";
    }
    
    const messageDiv = document.createElement("div");
    messageDiv.className = `message ${role}`;
    messageDiv.innerHTML = `<div class="message-content"><strong>${role === 'user' ? 'You' : 'Agnix'}:</strong><br>${content}</div>`;
    chatBox.appendChild(messageDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
}

// Send message
function sendMessage() {
    console.log("sendMessage() called");
    
    const input = document.getElementById("messageInput");
    if (!input) {
        console.error("Message input not found");
        return;
    }
    
    const message = input.value.trim();
    console.log("Message:", message);

    if (!message) {
        console.log("Empty message, not sending");
        return;
    }
    
    if (!socket) {
        console.error("No WebSocket connection");
        addMessageToChat("assistant", "⚠️ Not connected. Please refresh the page.");
        return;
    }
    
    if (socket.readyState !== WebSocket.OPEN) {
        console.error("WebSocket not open. State:", socket.readyState);
        addMessageToChat("assistant", "⚠️ Connecting... Please wait a moment.");
        return;
    }

    // Add user message to chat immediately
    addMessageToChat("user", message);
    
    // Send to server
    socket.send(message);
    console.log("Message sent");
    
    // Clear input
    input.value = "";
}

// Logout
function logout() {
    localStorage.removeItem("token");
    localStorage.removeItem("username");
    if (socket) socket.close();
    location.reload();
}
