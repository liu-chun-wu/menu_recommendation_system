const { defineConfig } = require('@vue/cli-service')
module.exports = defineConfig({
  transpileDependencies: true,
  publicPath: process.env.NODE_ENV === 'production'
  ?'GenAI-Tutor-Bootcamp-2025-team-5'
  :'/'
})
