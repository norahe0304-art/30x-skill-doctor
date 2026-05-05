"""
[INPUT]: 依赖 ./models 的 Category 与 SkillInstance。
[OUTPUT]: 对外提供 categorize(instance) -> Category，
         以及 PATH_PREFIX_RULES / KEYWORD_RULES 用于测试与可见性。
[POS]: 用途分类层。基于路径前缀优先 + description 关键词兜底匹配。
[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
"""

from __future__ import annotations

from .models import Category, SkillInstance

# 高优先级：路径前缀（命名空间式 skill 库通常用前缀）。
PATH_PREFIX_RULES: tuple[tuple[str, Category], ...] = (
    ("30x-seo-", Category.SEO),
    ("seo-", Category.SEO),
    ("ai-seo", Category.SEO),
    ("ads-", Category.ADS),
    ("ad-", Category.ADS),
    ("vercel:", Category.DEPLOY),
    ("vercel-", Category.DEPLOY),
    ("gsap-", Category.DEV),
    ("twelvelabs:", Category.AI_VIDEO),
    ("twelvelabs-", Category.AI_VIDEO),
    ("expo-", Category.DEV),
    ("native-", Category.DEV),
    ("apple-", Category.DESIGN),
    ("design-", Category.DESIGN),
    ("plan-", Category.DEV),
    ("ship", Category.DEV),
    ("review", Category.DEV),
    ("paid-ads", Category.ADS),
    ("page-cro", Category.MARKETING),
    ("popup-cro", Category.MARKETING),
    ("form-cro", Category.MARKETING),
    ("signup-flow-cro", Category.MARKETING),
    ("conversion-ops", Category.MARKETING),
    ("onboarding-cro", Category.MARKETING),
    ("paywall", Category.MARKETING),
    ("churn-", Category.MARKETING),
    ("referral-", Category.MARKETING),
    ("growth-", Category.MARKETING),
    ("pricing-", Category.MARKETING),
    ("launch-", Category.MARKETING),
    ("cold-email", Category.MARKETING),
    ("email-sequence", Category.MARKETING),
    ("linkedin-", Category.MARKETING),
    ("social-", Category.MARKETING),
    ("podcast-", Category.MARKETING),
    ("content-", Category.MARKETING),
    ("competitor-", Category.MARKETING),
    ("copywriting", Category.MARKETING),
    ("copy-editing", Category.MARKETING),
    ("sales-", Category.MARKETING),
    ("revenue-", Category.MARKETING),
    ("product-", Category.MARKETING),
    ("market-", Category.MARKETING),
    ("marketing-", Category.MARKETING),
    ("outbound-", Category.MARKETING),
    ("brand-", Category.MARKETING),
    ("schema-", Category.SEO),
    ("hreflang", Category.SEO),
    ("backlink", Category.SEO),
    ("sitemap", Category.SEO),
    ("redirect", Category.SEO),
    ("analytics-", Category.DATA),
    ("tracking-", Category.DATA),
    ("ab-test-", Category.DATA),
    ("revops", Category.DATA),
    ("conversion-", Category.DATA),
    ("seedance-", Category.AI_VIDEO),
    ("remotion-", Category.AI_VIDEO),
    ("ai-image-", Category.AI_VIDEO),
    ("twelvelabs:", Category.AI_VIDEO),
    ("animate", Category.AI_VIDEO),
    ("openai-", Category.DEV),
    ("ollama", Category.DEV),
    ("supabase", Category.DEV),
    ("postgres", Category.DEV),
)


# 关键词字典：先匹谁谁赢。description 转小写后做 substring 包含判断。
KEYWORD_RULES: tuple[tuple[Category, tuple[str, ...]], ...] = (
    (Category.SEO, (
        "seo", "search engine", "ranking", "serp", "keyword research", "backlink",
        "structured data", "schema markup", "internal linking", "ai search engine",
    )),
    (Category.ADS, (
        "ppc", "google ads", "meta ads", "ad campaign", "ad creative", "tiktok ads",
        "linkedin ads", "youtube ads", "microsoft ads", "paid advertising",
    )),
    (Category.MARKETING, (
        "copywriting", "marketing copy", "landing page", "email sequence",
        "newsletter", "linkedin post", "cold email", "growth marketing",
        "conversion rate", "launch", "pricing", "sales", "outbound", "referral",
        "product hunt", "go-to-market", "messaging",
    )),
    (Category.DEPLOY, (
        "deploy", "ci/cd", "production", "preview deployment", "vercel", "kubernetes",
        "edge function", "serverless", "infrastructure", "github actions",
    )),
    (Category.DATA, (
        "analytics", "tracking", "ga4", "metrics", "dashboard", "kpi", "attribution",
        "a/b test", "experiment", "cohort",
    )),
    (Category.DESIGN, (
        "figma", "design system", "typography", "color palette", "ui/ux", "ux",
        "human interface", "tailwind", "shadcn", "framer",
    )),
    (Category.AI_VIDEO, (
        "video", "image generation", "diffusion", "twelvelabs", "remotion",
        "stable diffusion", "midjourney", "image edit", "video edit",
    )),
    (Category.DEV, (
        "react component", "tsx", "refactor", "framework", "build script",
        "typescript", "nextjs", "next.js", "react native", "expo", "swift",
        "python", "rust", "golang", "code review", "test coverage",
    )),
)


def categorize(instance: SkillInstance) -> Category:
    """优先靠路径前缀，再靠 description 关键词，最后落到未分类。"""
    name_lower = instance.name.lower()
    for prefix, category in PATH_PREFIX_RULES:
        if name_lower.startswith(prefix):
            return category

    desc_lower = (instance.description or "").lower()
    if not desc_lower:
        return Category.UNCATEGORIZED

    for category, keywords in KEYWORD_RULES:
        if any(kw in desc_lower for kw in keywords):
            return category

    return Category.OTHER
