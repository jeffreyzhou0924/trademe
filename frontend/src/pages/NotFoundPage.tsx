import React from 'react'
import { Link } from 'react-router-dom'
import { Button } from '../components/common'

const NotFoundPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="text-center">
        <div className="mb-8">
          <div className="w-24 h-24 mx-auto bg-gray-200 rounded-full flex items-center justify-center mb-4">
            <span className="text-4xl">🔍</span>
          </div>
          <h1 className="text-6xl font-bold text-gray-900 mb-4">404</h1>
          <h2 className="text-2xl font-semibold text-gray-700 mb-2">页面未找到</h2>
          <p className="text-gray-500 mb-8">
            抱歉，您访问的页面不存在或已被移动
          </p>
        </div>
        
        <div className="space-x-4">
          <Link to="/">
            <Button>
              返回首页
            </Button>
          </Link>
          <Link to="/overview">
            <Button variant="outline">
              前往概览页
            </Button>
          </Link>
        </div>
      </div>
    </div>
  )
}

export default NotFoundPage