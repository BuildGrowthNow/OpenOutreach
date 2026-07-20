import Image from "next/image"

interface LogoProps {
  /** "dark" = white tree icon (for dark backgrounds like sidebar, navbar)
   *  "light" = dark tree icon (for light backgrounds like auth forms) */
  variant?: "dark" | "light"
  /** Size of the icon square in px */
  iconSize?: number
  className?: string
}

export function Logo({ variant = "dark", iconSize = 32, className = "" }: LogoProps) {
  const src = variant === "dark" ? "/logo-white.png" : "/logo-dark.png"

  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <div
        className="shrink-0 rounded-lg bg-emerald-500 flex items-center justify-center"
        style={{ width: iconSize, height: iconSize, padding: iconSize * 0.1 }}
      >
        <Image
          src={src}
          alt="Lengrowth"
          width={iconSize}
          height={iconSize}
          className="object-contain"
          priority
        />
      </div>
      <div className="flex flex-col leading-none">
        <span className="font-bold text-[1.05em] tracking-tight">Lengrowth</span>
        <span className="text-[0.6em] font-medium tracking-widest uppercase opacity-50 mt-0.5">
          Outreach
        </span>
      </div>
    </div>
  )
}
