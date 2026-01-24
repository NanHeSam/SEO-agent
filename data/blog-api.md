# Blog 博客管理接口文档

> 版本：v1.0
> 更新日期：2026-01-22
> 基础路径：`/admin/blogs`

---

## 目录

- [1. 创建博客](#1-创建博客)
- [2. 更新博客](#2-更新博客)
- [通用说明](#通用说明)

---

## 通用说明

### 认证方式

所有接口都需要在请求头中携带 JWT Token 进行身份认证。

| Header | 类型 | 必填 | 说明 |
|--------|------|:----:|------|
| token | String | ✅ | JWT Token，直接传 token 值 |

### 通用响应格式

```json
{
  "code": 0,
  "message": "success",
  "data": { ... }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| code | Integer | 状态码，0 表示成功，非 0 表示失败 |
| message | String | 响应消息 |
| data | Object | 响应数据 |

### 错误码说明

| code | 说明 |
|------|------|
| 0 | 成功 |
| 401 | 未授权/Token 无效 |
| 403 | 无权限访问 |
| 400 | 请求参数错误 |
| 500 | 服务器内部错误 |

---

## 1. 创建博客

创建一篇新的博客文章。

### 基本信息

| 项目 | 说明 |
|------|------|
| **接口路径** | `POST /admin/blogs` |
| **权限标识** | `blog:create_blog` |
| **Content-Type** | `application/json` |

### 请求参数

#### Request Body

| 参数名 | 类型 | 必填 | 说明 | 示例 |
|--------|------|:----:|------|------|
| slug | String | ✅ | URL 路径标识，用于生成文章访问链接，建议使用英文和短横线 | `"how-to-learn-java"` |
| title | String | ✅ | 博客标题 | `"Java 学习指南"` |
| author | String | ✅ | 作者名称 | `"张三"` |
| status | Integer | ✅ | 发布状态（0: 草稿, 1: 已发布, 2: 已下架） | `1` |
| summary | String | ❌ | 文章摘要，用于列表展示 | `"一篇关于Java学习的文章"` |
| content | String | ❌ | 正文内容，支持 HTML 格式 | `"<p>正文内容...</p>"` |
| coverUrl | String | ❌ | 封面图片 URL | `"https://cdn.example.com/cover.jpg"` |
| coverAlt | String | ❌ | 封面图片 alt 文本，用于 SEO 和无障碍访问 | `"Java 学习指南封面"` |
| publishTime | Long | ❌ | 发布时间，**秒级时间戳**。不传则使用当前时间 | `1705920000` |
| seoTitle | String | ❌ | SEO 标题，用于搜索引擎优化。不传则使用 title | `"Java学习指南 - LibaSpace"` |
| seoDescription | String | ❌ | SEO 描述，用于搜索引擎展示 | `"本文详细介绍了Java的学习路径..."` |
| keywords | String | ❌ | 关键词，多个关键词用逗号分隔 | `"Java,编程,学习"` |
| noIndex | Integer | ❌ | 是否禁止搜索引擎索引（0: 允许索引, 1: 禁止索引），默认 0 | `0` |

### 请求示例

```bash
curl -X POST 'https://api.example.com/admin/blogs' \
  -H 'token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...' \
  -H 'Content-Type: application/json' \
  -d '{
    "slug": "how-to-learn-java",
    "title": "Java 学习指南",
    "author": "张三",
    "status": 1,
    "summary": "一篇关于Java学习的文章，涵盖基础语法到高级特性",
    "content": "<h2>前言</h2><p>Java 是一门面向对象的编程语言...</p>",
    "coverUrl": "https://cdn.example.com/images/java-cover.jpg",
    "coverAlt": "Java 学习指南封面图",
    "publishTime": 1705920000,
    "seoTitle": "Java学习指南 - 从入门到精通 | LibaSpace",
    "seoDescription": "本文详细介绍了Java的学习路径，包括基础语法、面向对象、集合框架等核心知识点",
    "keywords": "Java,编程,学习,后端开发",
    "noIndex": 0
  }'
```

### 响应示例

#### 成功响应

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "success": true,
    "id": 10001
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| data.success | Boolean | 操作是否成功 |
| data.id | Long | 新创建的博客 ID |

#### 失败响应 - 参数校验错误

```json
{
  "code": 400,
  "message": "标题不能为空",
  "data": null
}
```

#### 失败响应 - 无权限

```json
{
  "code": 403,
  "message": "无权限访问",
  "data": null
}
```

---

## 2. 更新博客

更新已存在的博客文章。

### 基本信息

| 项目 | 说明 |
|------|------|
| **接口路径** | `PUT /admin/blogs/{id}` |
| **权限标识** | `blog:update_blog` |
| **Content-Type** | `application/json` |

### 请求参数

#### Path 参数

| 参数名 | 类型 | 必填 | 说明 | 示例 |
|--------|------|:----:|------|------|
| id | Long | ✅ | 博客 ID | `10001` |

#### Request Body

| 参数名 | 类型 | 必填 | 说明 | 示例 |
|--------|------|:----:|------|------|
| slug | String | ✅ | URL 路径标识 | `"how-to-learn-java-2024"` |
| title | String | ✅ | 博客标题 | `"Java 学习指南（更新版）"` |
| author | String | ✅ | 作者名称 | `"张三"` |
| status | Integer | ✅ | 发布状态（0: 草稿, 1: 已发布, 2: 已下架） | `1` |
| summary | String | ❌ | 文章摘要 | `"更新后的摘要..."` |
| content | String | ❌ | 正文内容 | `"<p>更新后的内容...</p>"` |
| coverUrl | String | ❌ | 封面图片 URL | `"https://cdn.example.com/new-cover.jpg"` |
| coverAlt | String | ❌ | 封面图片 alt 文本 | `"更新后的封面"` |
| publishTime | Long | ❌ | 发布时间（秒级时间戳） | `1706000000` |
| seoTitle | String | ❌ | SEO 标题 | `"Java学习指南2024版"` |
| seoDescription | String | ❌ | SEO 描述 | `"2024年更新版Java学习指南..."` |
| keywords | String | ❌ | 关键词 | `"Java,2024,编程"` |
| noIndex | Integer | ❌ | 是否禁止搜索引擎索引（0: 允许, 1: 禁止） | `0` |

### 请求示例

```bash
curl -X PUT 'https://api.example.com/admin/blogs/10001' \
  -H 'token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...' \
  -H 'Content-Type: application/json' \
  -d '{
    "slug": "how-to-learn-java-2024",
    "title": "Java 学习指南（2024 更新版）",
    "author": "张三",
    "status": 1,
    "summary": "2024年更新版Java学习指南，新增 Java 21 新特性介绍",
    "content": "<h2>前言</h2><p>本文已更新至 Java 21...</p>",
    "coverUrl": "https://cdn.example.com/images/java-cover-2024.jpg",
    "keywords": "Java,Java21,编程,学习,2024"
  }'
```

### 响应示例

#### 成功响应

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "success": true,
    "id": 10001
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| data.success | Boolean | 操作是否成功 |
| data.id | Long | 更新的博客 ID |

#### 失败响应 - 博客不存在

```json
{
  "code": 404,
  "message": "博客不存在",
  "data": null
}
```

#### 失败响应 - 参数校验错误

```json
{
  "code": 400,
  "message": "Slug不能为空",
  "data": null
}
```

---

## 附录

### A. 状态值说明

| status | 说明 |
|:------:|------|
| 0 | 草稿 - 仅后台可见 |
| 1 | 已发布 - 前台可访问 |
| 2 | 已下架 - 前台不可访问 |

### B. 字段长度建议

| 字段 | 建议长度 |
|------|----------|
| slug | ≤ 200 字符 |
| title | ≤ 200 字符 |
| summary | ≤ 500 字符 |
| seoTitle | ≤ 70 字符（Google 建议） |
| seoDescription | ≤ 160 字符（Google 建议） |
| keywords | ≤ 200 字符 |

### C. 注意事项

1. **slug 唯一性**：slug 用于生成文章 URL，应保证唯一性
2. **时间戳格式**：publishTime 为**秒级**时间戳，不是毫秒级
3. **HTML 内容**：content 字段支持 HTML，前端需做好 XSS 防护
4. **SEO 字段**：seoTitle 和 seoDescription 如不填写，前端可降级使用 title 和 summary
