import { LazyMotion, MotionConfig } from 'framer-motion'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { ToastProvider } from './components/shell/Toast'

const loadMotionFeatures = () => import('./lib/motionFeatures').then((mod) => mod.default)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {/* reducedMotion="user": when the OS asks for less motion, transforms are skipped and only fades remain. */}
    <MotionConfig reducedMotion="user">
      {/* Animation features load after first paint, keeping them out of the main bundle. */}
      <LazyMotion features={loadMotionFeatures} strict>
        <ToastProvider>
          <App />
        </ToastProvider>
      </LazyMotion>
    </MotionConfig>
  </StrictMode>,
)
