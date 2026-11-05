import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// `npm run dev` serves the app on http://localhost:5173 and forwards /api to the backend
// on port 8000 (for example `docker compose up backend`), like nginx does in Docker.
// 127.0.0.1 and not "localhost": on Windows, Node may try the IPv6 address first and miss
// the backend. Set API_TARGET to use another address.
// `npm test` runs the Vitest tests in src/ in a simulated browser (jsdom).
const API_TARGET = process.env.API_TARGET ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: API_TARGET,
        configure(proxy) {
          // Without a backend, say so in the page instead of a bare "500".
          proxy.on('error', (_error, _req, res) => {
            if (res.headersSent || !res.writeHead) return
            res.writeHead(502, { 'Content-Type': 'application/json' })
            res.end(
              JSON.stringify({
                error: {
                  code: 'BACKEND_DOWN',
                  message: `The backend is not answering on ${API_TARGET}. Start it with "docker compose up backend" and reload.`,
                },
              }),
            )
          })
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.js'],
    testTimeout: 15000,
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{js,jsx}'],
      exclude: ['src/main.jsx', 'src/test/**', 'src/**/*.test.{js,jsx}'],
      reporter: ['text-summary', 'text', 'html', 'json-summary'],
      thresholds: { lines: 60 },
    },
  },
})
