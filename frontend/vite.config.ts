import { defineConfig } from 'vite'; import react from '@vitejs/plugin-react';
export default defineConfig({plugins:[react()],server:{port:Number(process.env.PORT)||5173,proxy:{'/api':'http://localhost:8000','/ws':{target:'ws://localhost:8000',ws:true}}},test:{environment:'jsdom'}});
