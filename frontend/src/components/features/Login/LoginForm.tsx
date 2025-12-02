/**
 * Login form component
 */

import { useState, type FormEvent } from 'react'
import { ArrowRight } from 'lucide-react'
import { Button, Input } from '@/components/ui'
import { useAppStore } from '@/store'
import { useToast } from '@/hooks/useToast'
import { login } from '@/api/client'

export function LoginForm() {
  const [email, setEmail] = useState('demo@example.com')
  const [password, setPassword] = useState('demo')
  const [isLoading, setIsLoading] = useState(false)
  const { setToken } = useAppStore()
  const toast = useToast()

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setIsLoading(true)

    try {
      const response = await login({ username: email, password })
      setToken(response.token)
      toast.success('Login successful!')
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Login failed'
      toast.error(message)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="animate-fade-in">
      {/* Floating boxes illustration */}
      <div className="relative h-32 mb-8 flex items-center justify-center">
        <div className="absolute w-16 h-16 rounded-xl bg-gradient-to-br from-indigo-500/30 to-pink-500/30 border border-white/10 animate-float" />
        <div className="absolute left-1/4 top-4 w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500/20 to-pink-500/20 border border-white/10 animate-float opacity-70" style={{ animationDelay: '-1.5s' }} />
        <div className="absolute right-1/4 bottom-4 w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500/15 to-pink-500/15 border border-white/10 animate-float opacity-50" style={{ animationDelay: '-3s' }} />
      </div>

      <h1 className="text-3xl font-bold gradient-text text-center mb-2">
        Welcome to Homebox
      </h1>
      <p className="text-gray-400 text-center mb-8">
        Scan and organize your inventory with AI-powered detection
      </p>

      <form onSubmit={handleSubmit} className="space-y-6">
        <Input
          type="email"
          label="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Enter your email"
          required
        />

        <Input
          type="password"
          label="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Enter your password"
          required
        />

        <Button type="submit" fullWidth isLoading={isLoading}>
          <span>Sign In</span>
          <ArrowRight className="w-5 h-5" />
        </Button>
      </form>
    </div>
  )
}
