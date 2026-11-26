/**
 * 首页空状态组件
 * 居中展示欢迎信息和引导语，示例问题由输入框弹层提供
 */
import { Sparkles } from "lucide-react";

export function EmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center px-6 py-16 text-center">
      <div className="grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br from-brand to-[#7B8CFF] text-white shadow-float">
        <Sparkles className="h-7 w-7" aria-hidden="true" />
      </div>

      <h1 className="mt-6 text-balance text-3xl font-semibold tracking-tight text-ink sm:text-[2.5rem] sm:leading-tight">
        你好，我是问数助手
      </h1>

      <p className="mt-3 max-w-md text-[15px] leading-7 text-muted">
        用一句话描述你想看的电商数据，剩下的交给我。
      </p>

      <div className="mt-8 inline-flex items-center gap-1.5 rounded-full bg-brandSoft px-3 py-1.5 text-xs text-brand/80">
        <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
        点击下方输入框，可以先看几个示例
      </div>
    </div>
  );
}
