import React, { useState } from 'react'
import { PhotoIcon } from '@heroicons/react/24/outline'
import ImagePasteModal from './ImagePasteModal'

interface ImagePasteButtonProps {
  className?: string
}

export const ImagePasteButton: React.FC<ImagePasteButtonProps> = ({
  className = ''
}) => {
  const [isModalOpen, setIsModalOpen] = useState(false)

  return (
    <>
      {/* 浮动按钮 */}
      <button
        onClick={() => setIsModalOpen(true)}
        className={`
          fixed bottom-6 right-6 z-40
          bg-blue-600 hover:bg-blue-700
          text-white rounded-full
          w-14 h-14
          flex items-center justify-center
          shadow-lg hover:shadow-xl
          transition-all duration-200
          group
          ${className}
        `}
        title="粘贴图片讨论"
      >
        <PhotoIcon className="w-6 h-6 group-hover:scale-110 transition-transform" />

        {/* 提示文字 */}
        <div className="
          absolute right-16 bottom-2
          bg-gray-800 text-white text-xs
          px-2 py-1 rounded
          opacity-0 group-hover:opacity-100
          transition-opacity duration-200
          whitespace-nowrap
          pointer-events-none
        ">
          截图讨论前端问题
        </div>
      </button>

      {/* 图片粘贴模态框 */}
      <ImagePasteModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
      />
    </>
  )
}

export default ImagePasteButton