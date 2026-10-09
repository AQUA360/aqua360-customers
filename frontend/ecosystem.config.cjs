module.exports = {
  apps: [
    {
      name: 'Aqua Customers Frontend',
      exec_mode: 'cluster',
      instances: 'max',
      script: './.output/server/index.mjs',
      env: {
         "NITRO_PORT": 3005,
         "NITRO_HOST": "127.0.0.1",
      }
    }
  ]
}