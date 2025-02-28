<template>
  <div class="d-flex flex-column align-items-center min-vh-100 bg-light p-4">
    <!-- 標題 -->
    <h1 class="text-primary mb-4">RAG 聊天系統</h1>

    <!-- 聊天框 -->
    <div
      class="w-100 max-w-3xl bg-white shadow rounded p-4 h-500 overflow-auto border border-secondary position-relative">
      <!-- 左上角：上傳檔案 -->
      <input type="file" @change="handleFileUpload"
        class="position-absolute top-0 start-0 m-2 btn btn-outline-secondary btn-sm" />

      <!-- 右上角：清除聊天 -->
      <button class="position-absolute top-0 end-0 m-2 btn btn-danger btn-sm" @click="clearChat">
        清除聊天
      </button>

      <!-- 聊天內容 -->
      <div v-for="message in messages" :key="message.id"
        :class="message.sender === 'User' ? 'bg-white text-black text-end' : 'bg-light text-start'"
        class="p-3 my-2 rounded w-75 mx-auto">
        <strong class="text-dark">{{ message.sender }}:</strong>
        <p class="m-0" v-html="message.text"></p> <!-- 這裡用 v-html 來顯示解析後的 HTML -->
      </div>
    </div>

    <!-- 底部輸入框 -->
    <div class="w-100 max-w-3xl mt-4 d-flex gap-2">
      <input v-model="userMessage" class="form-control" placeholder="請輸入你的消息..." @keyup.enter="sendMessage" />
      <button class="btn btn-primary" @click="sendMessage">
        發送
      </button>
    </div>
  </div>
</template>

<script>
import axios from "axios";
import { marked } from "marked";

export default {
  data() {
    return {
      userMessage: "",
      messages: [],
    };
  },
  methods: {
    sendMessage() {
      if (this.userMessage.trim() === "") return;

      const userMsg = this.userMessage;
      this.messages.push({ id: Date.now(), sender: "User", text: userMsg });

      axios
        .post("http://localhost:5000/respond", { user_message: userMsg })
        .then((response) => {
          const botMessage = response.data.bot_message;
          const formattedMessage = marked(botMessage); // 解析 Markdown

          this.messages.push({ id: Date.now(), sender: "Your waiter", text: formattedMessage });
        })
        .catch((error) => {
          console.error("Error sending message:", error);
        });

      this.userMessage = "";
    },

    handleFileUpload(event) {
      const formData = new FormData();
      formData.append("file", event.target.files[0]);

      axios
        .post("http://localhost:5000/upload", formData)
        .then((response) => {
          alert(response.data);
        })
        .catch((error) => {
          console.error("Error uploading file:", error);
        });
    },

    clearChat() {
      this.messages = [];
    },
  },
};
</script>

<style scoped>
@import url('https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css');

.h-500 {
  height: 500px;
}
</style>