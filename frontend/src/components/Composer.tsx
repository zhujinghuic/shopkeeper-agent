/**
 * 聊天输入区组件
 * 聚焦输入框时在下方弹出示例问题，点击即可填入，开始输入后自动收起
 */
import { ArrowUp, Sparkles, Square } from "lucide-react";
import { FormEvent, KeyboardEvent, useRef, useState } from "react";
import { cn } from "../lib/format";

type ComposerProps = {
    value: string;
    disabled: boolean;
    isStreaming: boolean;
    examples: string[];
    onChange: (value: string) => void;
    onSubmit: () => void;
    onStop: () => void;
};

export function Composer({
    value,
    disabled,
    isStreaming,
    examples,
    onChange,
    onSubmit,
    onStop,
}: ComposerProps) {
    const textareaRef = useRef<HTMLTextAreaElement | null>(null);
    const [showExamples, setShowExamples] = useState(false);

    const submit = (event: FormEvent) => {
        event.preventDefault();
        if (!disabled) onSubmit();
    };

    const handleChange = (next: string) => {
        onChange(next);
        // 只要开始输入，就把示例收起来
        if (next.trim().length > 0) setShowExamples(false);
    };

    const pickExample = (example: string) => {
        onChange(example);
        setShowExamples(false);
        textareaRef.current?.focus();
    };

    const handleFocus = () => {
        if (value.trim().length === 0) setShowExamples(true);
    };

    const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
        if (event.key === "Escape") {
            setShowExamples(false);
            return;
        }

        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            if (!disabled) onSubmit();
        }
    };

    return (
        <div className="relative mx-auto w-full max-w-3xl">
            {showExamples && examples.length > 0 && (
                <div className="absolute bottom-full left-0 right-0 mb-2 animate-pop-in overflow-hidden rounded-2xl border border-line bg-surface p-2 shadow-float">
                    <div className="px-2.5 pb-1 pt-1.5 text-[11px] font-medium tracking-wide text-muted">
                        换个问法试试
                    </div>
                    {examples.map((example) => (
                        <button
                            key={example}
                            type="button"
                            // 阻止默认行为以保持输入框焦点，保证点击能正常触发
                            onMouseDown={(event) => event.preventDefault()}
                            onClick={() => pickExample(example)}
                            className="flex w-full items-start gap-2.5 rounded-xl px-2.5 py-2.5 text-left text-[13.5px] leading-5 text-ink/75 transition hover:bg-brandSoft hover:text-ink"
                        >
                            <Sparkles
                                className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand/60"
                                aria-hidden="true"
                            />
                            <span>{example}</span>
                        </button>
                    ))}
                </div>
            )}

            <form onSubmit={submit}>
                <div className="flex items-end gap-2 rounded-[26px] border border-line bg-surface p-2 pl-4 shadow-soft transition focus-within:border-brand/35 focus-within:shadow-[0_0_0_4px_rgba(77,107,254,0.08)]">
                    <textarea
                        ref={textareaRef}
                        value={value}
                        onChange={(event) => handleChange(event.target.value)}
                        onFocus={handleFocus}
                        onBlur={() => setShowExamples(false)}
                        onKeyDown={onKeyDown}
                        rows={1}
                        placeholder="问一个电商数据问题…"
                        className="max-h-36 min-h-11 flex-1 resize-none bg-transparent py-3 text-[15px] leading-6 text-ink outline-none placeholder:text-muted/70"
                    />
                    <button
                        type={isStreaming ? "button" : "submit"}
                        onClick={isStreaming ? onStop : undefined}
                        disabled={!isStreaming && disabled}
                        className={cn(
                            "grid h-9 w-9 shrink-0 place-items-center rounded-full transition",
                            isStreaming
                                ? "bg-ink text-surface hover:bg-ink/85"
                                : "bg-brand text-white hover:bg-brandDeep disabled:cursor-not-allowed disabled:bg-line disabled:text-muted/60",
                        )}
                        title={isStreaming ? "停止" : "发送"}
                        aria-label={isStreaming ? "停止" : "发送"}
                    >
                        {isStreaming ? (
                            <Square className="h-3.5 w-3.5 fill-current" aria-hidden="true" />
                        ) : (
                            <ArrowUp className="h-4 w-4" aria-hidden="true" />
                        )}
                    </button>
                </div>
                <p className="mt-2 text-center text-[11px] text-muted/70">
                    Enter 发送 · Shift + Enter 换行
                </p>
            </form>
        </div>
    );
}
