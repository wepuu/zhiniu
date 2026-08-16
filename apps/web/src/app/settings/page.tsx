import { AppShell } from "@/components/app-shell";
import { PageHeading } from "@/components/page-heading";
import { Card } from "@/components/ui/card";

export default function SettingsPage() {
  return (
    <AppShell>
      <PageHeading
        eyebrow="Preferences"
        title="研究偏好"
        description="管理界面、通知和研究摘要偏好。账户与套餐能力将在后续阶段接入。"
      />
      <div className="mt-6 max-w-2xl space-y-4">
        <Card className="p-5">
          <h2 className="font-medium">界面密度</h2>
          <p className="text-slate mt-1 text-sm">
            桌面端使用研究工作区密度，移动端使用可触控卡片。
          </p>
        </Card>
        <Card className="p-5">
          <h2 className="font-medium">风险提示</h2>
          <p className="text-slate mt-1 text-sm">
            所有研究输出保持描述性，不提供买卖或目标价建议。
          </p>
        </Card>
      </div>
    </AppShell>
  );
}
