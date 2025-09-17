import React, { useState, useRef, useCallback } from 'react'
import { XMarkIcon, PhotoIcon, DocumentDuplicateIcon, CheckIcon } from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'
import { useAuthStore } from '../../store/authStore'

interface ImagePasteModalProps {
  isOpen: boolean
  onClose: () => void
}

interface UploadedImage {
  id: string
  filename: string
  url: string
  uploadTime: string
  size: number
}

export const ImagePasteModal: React.FC<ImagePasteModalProps> = ({
  isOpen,
  onClose
}) => {
  const [dragActive, setDragActive] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadedImages, setUploadedImages] = useState<UploadedImage[]>([])
  const [pasteArea, setPasteArea] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)
  const pasteAreaRef = useRef<HTMLDivElement>(null)
  const { token } = useAuthStore()

  // 处理拖拽
  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true)
    } else if (e.type === "dragleave") {
      setDragActive(false)
    }
  }, [])

  // 处理拖拽释放
  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFiles(Array.from(e.dataTransfer.files))
    }
  }, [])

  // 处理粘贴事件
  const handlePaste = useCallback(async (e: React.ClipboardEvent) => {
    const items = e.clipboardData?.items
    if (!items) return

    const files: File[] = []
    for (let i = 0; i < items.length; i++) {
      const item = items[i]
      if (item.type.indexOf('image') !== -1) {
        const file = item.getAsFile()
        if (file) {
          files.push(file)
        }
      }
    }

    if (files.length > 0) {
      e.preventDefault()
      handleFiles(files)
    }
  }, [])

  // 处理文件选择
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      handleFiles(Array.from(e.target.files))
    }
  }

  // 统一文件处理
  const handleFiles = async (files: File[]) => {
    const imageFiles = files.filter(file => file.type.startsWith('image/'))

    if (imageFiles.length === 0) {
      toast.error('请选择图片文件')
      return
    }

    for (const file of imageFiles) {
      await uploadImage(file)
    }
  }

  // 上传图片
  const uploadImage = async (file: File) => {
    if (!token) {
      toast.error('请先登录')
      return
    }

    setUploading(true)
    try {
      const formData = new FormData()
      formData.append('image', file)
      formData.append('purpose', 'debug_discussion')

      const response = await fetch('/api/v1/debug/upload-image', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      })

      if (!response.ok) {
        throw new Error('上传失败')
      }

      const result = await response.json()

      const newImage: UploadedImage = {
        id: result.id,
        filename: result.filename,
        url: result.url,
        uploadTime: new Date().toLocaleString(),
        size: file.size
      }

      setUploadedImages(prev => [newImage, ...prev])
      toast.success(`图片上传成功: ${result.filename}`)

      // 自动复制文件路径
      const fullPath = `/root/trademe/uploads/debug/${result.filename}`
      await navigator.clipboard.writeText(fullPath)
      toast.success('文件路径已复制到剪贴板')

    } catch (error) {
      console.error('上传图片失败:', error)
      toast.error('上传图片失败，请重试')
    } finally {
      setUploading(false)
    }
  }

  // 格式化文件大小
  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  }

  // 复制路径
  const copyPath = async (filename: string) => {
    const fullPath = `/root/trademe/uploads/debug/${filename}`
    try {
      await navigator.clipboard.writeText(fullPath)
      toast.success('路径已复制')
    } catch (error) {
      toast.error('复制失败')
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-hidden">
        {/* 头部 */}
        <div className="flex items-center justify-between p-4 border-b">
          <div className="flex items-center space-x-2">
            <PhotoIcon className="w-6 h-6 text-blue-600" />
            <h2 className="text-lg font-semibold text-gray-900">图片粘贴助手</h2>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            <XMarkIcon className="w-6 h-6" />
          </button>
        </div>

        {/* 内容区域 */}
        <div className="p-4 space-y-4">
          {/* 使用说明 */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
            <h3 className="text-sm font-medium text-blue-800 mb-1">使用方法：</h3>
            <ul className="text-sm text-blue-700 space-y-1">
              <li>• 直接在下方区域 <kbd className="px-1 py-0.5 bg-blue-100 rounded">Ctrl+V</kbd> 粘贴截图</li>
              <li>• 拖拽图片文件到虚线区域</li>
              <li>• 点击选择文件按钮上传</li>
              <li>• 上传后自动复制文件路径，方便Claude查看</li>
            </ul>
          </div>

          {/* 粘贴/拖拽区域 */}
          <div
            ref={pasteAreaRef}
            className={`
              border-2 border-dashed rounded-lg p-8 text-center transition-colors
              ${dragActive
                ? 'border-blue-500 bg-blue-50'
                : 'border-gray-300 hover:border-gray-400'
              }
              ${uploading ? 'opacity-50 pointer-events-none' : ''}
            `}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            onPaste={handlePaste}
            tabIndex={0}
          >
            <PhotoIcon className="w-12 h-12 text-gray-400 mx-auto mb-2" />
            <div className="text-gray-600">
              {uploading ? (
                <div className="flex items-center justify-center space-x-2">
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
                  <span>上传中...</span>
                </div>
              ) : (
                <>
                  <p className="text-lg font-medium">点击此区域并粘贴图片 (Ctrl+V)</p>
                  <p className="text-sm text-gray-500 mt-1">
                    或拖拽图片文件到这里
                  </p>
                </>
              )}
            </div>

            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept="image/*"
              onChange={handleFileSelect}
              className="hidden"
            />

            {!uploading && (
              <button
                onClick={() => fileInputRef.current?.click()}
                className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
              >
                选择文件
              </button>
            )}
          </div>

          {/* 已上传图片列表 */}
          {uploadedImages.length > 0 && (
            <div className="space-y-2">
              <h3 className="font-medium text-gray-900">已上传图片:</h3>
              <div className="max-h-48 overflow-y-auto space-y-2">
                {uploadedImages.map((image) => (
                  <div
                    key={image.id}
                    className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                  >
                    <div className="flex items-center space-x-3">
                      <img
                        src={image.url}
                        alt={image.filename}
                        className="w-10 h-10 object-cover rounded"
                      />
                      <div>
                        <div className="text-sm font-medium text-gray-900">
                          {image.filename}
                        </div>
                        <div className="text-xs text-gray-500">
                          {formatFileSize(image.size)} • {image.uploadTime}
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={() => copyPath(image.filename)}
                      className="flex items-center space-x-1 px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200 transition-colors"
                    >
                      <DocumentDuplicateIcon className="w-3 h-3" />
                      <span>复制路径</span>
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* 底部 */}
        <div className="border-t p-4 bg-gray-50">
          <div className="flex justify-between items-center">
            <div className="text-sm text-gray-600">
              💡 上传的图片会保存到 <code className="bg-gray-200 px-1 rounded">/root/trademe/uploads/debug/</code>
            </div>
            <button
              onClick={onClose}
              className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 transition-colors"
            >
              关闭
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ImagePasteModal