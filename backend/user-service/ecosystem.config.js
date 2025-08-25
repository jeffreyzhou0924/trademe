module.exports = {
  apps: [{
    name: 'trademe-user-service',
    script: 'dist/app.js',
    cwd: '/root/trademe/backend/user-service',
    instances: 2,
    exec_mode: 'cluster',
    env: {
      NODE_ENV: 'production',
      PORT: 3001
    },
    env_development: {
      NODE_ENV: 'development',
      PORT: 3001
    },
    log_file: '/root/trademe/logs/user-service.log',
    error_file: '/root/trademe/logs/user-service-error.log',
    out_file: '/root/trademe/logs/user-service-out.log',
    log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
    merge_logs: true,
    max_memory_restart: '500M',
    restart_delay: 4000,
    max_restarts: 10,
    min_uptime: '10s',
    watch: false,
    ignore_watch: ['node_modules', 'logs'],
    node_args: '-r tsconfig-paths/register',
    kill_timeout: 5000,
    listen_timeout: 8000,
    shutdown_with_message: true,
    wait_ready: true,
    autorestart: true,
    vizion: false
  }]
};