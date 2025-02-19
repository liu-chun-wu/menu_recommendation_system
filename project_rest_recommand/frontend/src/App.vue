<template>
  <div>
    <h1>RAG 聊天系統</h1>

    <!-- 顯示聊天訊息 -->
    <div v-for="message in messages" :key="message.id" class="chat-message">
      <strong>{{ message.sender }}:</strong> {{ message.text }}
    </div>

    <!-- 用戶輸入框 -->
    <input v-model="userMessage" placeholder="請輸入你的消息..." @keyup.enter="sendMessage" />

    <!-- 上傳文件 -->
    <input type="file" @change="handleFileUpload" />

    <!-- 清除聊天 -->
    <button @click="clearChat">清除聊天</button>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  data() {
    return {
      userMessage: '',
      messages: [],
    };
  },
  methods: {
    // 發送消息
    sendMessage() {
      if (this.userMessage.trim() === '') return;
      
      const userMsg = this.userMessage;
      this.messages.push({ id: Date.now(), sender: 'User', text: userMsg });

      axios.post('http://localhost:5000/respond', { user_message: userMsg })
        .then((response) => {
          const botMessage = response.data.bot_message.split('\n').map(line => line.trim()).filter(line => line !== "");
          botMessage.forEach((line) => {
          this.messages.push({ id: Date.now(), sender: 'Bot', text: line });
        });
          
        })
        .catch((error) => {
          console.error('Error sending message:', error);
        });

      // 清空輸入框
      this.userMessage = '';
    },

    // 處理文件上傳
    handleFileUpload(event) {
      const formData = new FormData();
      formData.append('file', event.target.files[0]);

      axios.post('http://localhost:5000/upload', formData)
        .then((response) => {
          alert('文件上傳成功: ' + response.data);
        })
        .catch((error) => {
          console.error('Error uploading file:', error);
        });
    },

    // 清除聊天
    clearChat() {
      this.messages = [];
    },
  },
};
</script>

<style scoped>
.chat-message {
  margin-bottom: 10px;
}
</style>
