import React, { useState, useMemo } from 'react';
import { Row, Col, Card, DatePicker, Typography } from 'antd';
import { useNavigate } from 'react-router-dom';
import {
  FileTextOutlined,
  TeamOutlined,
  FieldStringOutlined,
  TagOutlined,
} from '@ant-design/icons';
import type { Dayjs } from 'dayjs';
import KpiCard from '../components/common/KpiCard';
import EChartsWrapper from '../components/charts/EChartsWrapper';
import { useSummary, useCategories, useDailyCounts, useLanguage } from '../hooks/useAnalysisData';

const { RangePicker } = DatePicker;
const { Text } = Typography;

function formatDate(d: string): string {
  if (!d) return '';
  if (d.length === 8 && !d.includes('-')) {
    return `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}`;
  }
  return d;
}

// Clickable keyword that navigates to a route
const Kw: React.FC<{ to: string; children: React.ReactNode }> = ({ to, children }) => {
  const navigate = useNavigate();
  return (
    <span
      onClick={() => navigate(to)}
      style={{ fontWeight: 700, color: '#1677ff', cursor: 'pointer', textDecoration: 'underline dotted' }}
    >
      {children}
    </span>
  );
};

interface InsightData {
  total: number;
  users: number;
  perUser: number;
  avgLen: number;
  cats: { name: string; count: number }[];
  totalCat: number;
  styles: { name: string; count: number }[];
  totalStyle: number;
  langs: { language: string; count: number }[];
  totalLang: number;
  langCount: number;
}

function buildInsight(d: InsightData): React.ReactNode {
  const { total, users, perUser, avgLen, cats, totalCat, styles, totalStyle, langs, totalLang, langCount } = d;

  const pct = (n: number, t: number) => t > 0 ? ((n / t) * 100).toFixed(0) : '0';

  const top1 = cats[0];
  const top2 = cats[1];
  const top1Pct = top1 ? pct(top1.count, totalCat) : '0';
  const top2Pct = top2 ? pct(top2.count, totalCat) : '0';
  const top12Pct = top1 && top2 ? ((top1.count + top2.count) / totalCat * 100).toFixed(0) : '0';

  const topStyle = styles[0];
  const topStylePct = topStyle ? pct(topStyle.count, totalStyle) : '0';

  const enLike = langs.find(l => l.language?.toLowerCase().includes('en'));
  const enPct = enLike ? pct(enLike.count, totalLang) : '0';

  const lenQuality = avgLen < 80 ? '偏短' : avgLen < 150 ? '适中' : '较长';
  const lenDesc = avgLen < 80
    ? '用户描述较简单，有引导用户细化 Prompt 的空间'
    : avgLen < 150
    ? '用户具备一定描述能力，整体质量中等'
    : '用户描述详细，整体 Prompt 质量较高，为生成效果打下基础';

  const perUserNum = perUser;
  const retentionDesc = perUserNum < 2
    ? '人均创作量偏低，用户单次使用后复访意愿不足'
    : perUserNum < 5
    ? '用户粘性良好，复访率有进一步提升空间'
    : '用户粘性强，高频创作用户占比可观';

  // Module 1: 核心业务现状
  const mod1 = (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontWeight: 700, color: '#0958d9', marginBottom: 6, fontSize: 13 }}>核心业务现状</div>
      <div style={{ lineHeight: 1.9, fontSize: 13 }}>
        平台累计生成 <b>{total.toLocaleString()}</b> 条 Prompt，服务 <b>{users.toLocaleString()}</b> 位独立用户，
        人均创作 <b>{perUserNum.toFixed(1)}</b> 条，{retentionDesc}。
        核心需求集中于{top1 && <><Kw to="/categories">「{top1.name}」</Kw>（{top1Pct}%）</>}
        {top2 && <>与<Kw to="/categories">「{top2.name}」</Kw>（{top2Pct}%）</>}，
        合计占比 <b>{top12Pct}%</b>；
        {topStyle && <>主流风格为<Kw to="/categories">「{topStyle.name}」</Kw>，占比 <b>{topStylePct}%</b>；</>}
        {enLike && <>英文用户占比 <b>{enPct}%</b>，覆盖 <b>{langCount}</b> 种语言，已具备国际化基础。</>}
      </div>
    </div>
  );

  // Module 2: 关键数据洞察
  const insights: React.ReactNode[] = [];

  insights.push(
    <div key="retention">
      <b>① 用户活跃度：</b>人均创作 <b>{perUserNum.toFixed(1)}</b> 条，{retentionDesc}，
      建议通过爆款模板与 Prompt 优化引导提升复访率。
    </div>
  );

  if (top1 && top2) {
    insights.push(
      <div key="demand">
        <b>② 需求集中度：</b>
        <Kw to="/categories">{top1.name}</Kw> + <Kw to="/categories">{top2.name}</Kw> 合计占比 <b>{top12Pct}%</b>，
        核心需求明确，建议优先投入资源优化这两类场景的生成效果。
      </div>
    );
  }

  if (topStyle) {
    insights.push(
      <div key="style">
        <b>③ 风格偏好：</b>
        <Kw to="/categories">{topStyle.name}</Kw> 风格占比 <b>{topStylePct}%</b>，
        是用户核心审美需求，需重点优化该风格渲染的精度与细节表现。
      </div>
    );
  }

  if (avgLen > 0) {
    insights.push(
      <div key="quality">
        <b>④ Prompt 质量：</b>平均长度 <b>{avgLen}</b> 字符，整体{lenQuality}，{lenDesc}。
      </div>
    );
  }

  if (enLike) {
    insights.push(
      <div key="i18n">
        <b>⑤ 国际化布局：</b>英文用户占比 <b>{enPct}%</b>，覆盖 <b>{langCount}</b> 种语言，
        平台已具备全球化用户基础，需针对性优化多语言 Prompt 模板与引导体验。
      </div>
    );
  }

  const mod2 = (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontWeight: 700, color: '#0958d9', marginBottom: 6, fontSize: 13 }}>关键数据洞察</div>
      <div style={{ lineHeight: 2.1, fontSize: 13, display: 'flex', flexDirection: 'column', gap: 2 }}>
        {insights}
      </div>
    </div>
  );

  // Module 3: 问题诊断
  const problems: React.ReactNode[] = [];

  if (Number(top12Pct) > 50) {
    problems.push(
      <div key="p1">
        <b>① 需求集中度过高：</b>Top 2 类别占比 <b>{top12Pct}%</b>，
        长尾需求覆盖不足，用户多样化创作场景有待拓展。
      </div>
    );
  }

  if (topStyle && Number(topStylePct) > 45) {
    problems.push(
      <div key="p2">
        <b>② 风格单一化风险：</b>{topStyle.name} 风格占比超 <b>{topStylePct}%</b>，
        其他风格占比偏低，需丰富风格模板，满足多元审美需求。
      </div>
    );
  }

  if (perUserNum < 3) {
    problems.push(
      <div key="p3">
        <b>③ 用户留存待提升：</b>人均创作仅 <b>{perUserNum.toFixed(1)}</b> 条，
        说明用户单次使用后复访意愿不足，需通过模板推荐、效果引导提升用户留存。
      </div>
    );
  }

  if (avgLen < 80) {
    problems.push(
      <div key="p4">
        <b>④ Prompt 质量偏低：</b>平均长度仅 <b>{avgLen}</b> 字符，
        用户描述过于简单，生成效果可能受限，需加强 Prompt 引导与优化提示。
      </div>
    );
  }

  const mod3 = problems.length > 0 ? (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontWeight: 700, color: '#0958d9', marginBottom: 6, fontSize: 13 }}>问题诊断与风险提示</div>
      <div style={{ lineHeight: 2.1, fontSize: 13, display: 'flex', flexDirection: 'column', gap: 2 }}>
        {problems}
      </div>
    </div>
  ) : null;

  // Module 4: 优化建议
  const suggestions: React.ReactNode[] = [];

  if (top1 && top2) {
    suggestions.push(
      <div key="s1">
        <b>① 聚焦核心场景：</b>针对 <Kw to="/categories">{top1.name}</Kw>、
        <Kw to="/categories">{top2.name}</Kw> 两大核心类别，
        优化生成模型精度，补充专属 Prompt 模板，提升核心用户体验与满意度。
      </div>
    );
  }

  if (topStyle && Number(topStylePct) > 40) {
    suggestions.push(
      <div key="s2">
        <b>② 丰富风格生态：</b>在强化 <Kw to="/categories">{topStyle.name}</Kw> 风格渲染能力的同时，
        针对卡通、赛博朋克等潜力风格新增模板库，引导用户尝试多元风格，提升平台风格多样性。
      </div>
    );
  }

  suggestions.push(
    <div key="s3">
      <b>③ 提升用户留存：</b>通过爆款模板推荐、Prompt 优化建议、生成效果对比展示，
      提升用户生成体验，进而提升人均创作量与复访率。
    </div>
  );

  if (avgLen < 120) {
    suggestions.push(
      <div key="s4">
        <b>④ 引导 Prompt 质量提升：</b>在创作入口增加 Prompt 优化提示与示例，
        引导用户补充细节描述，提升平均 Prompt 质量，改善生成效果。
      </div>
    );
  }

  if (enLike) {
    suggestions.push(
      <div key="s5">
        <b>⑤ 强化国际化运营：</b>针对英文用户优化多语言 Prompt 引导，
        补充英文爆款模板，扩大国际化用户规模，提升平台全球竞争力。
      </div>
    );
  }

  const mod4 = (
    <div>
      <div style={{ fontWeight: 700, color: '#0958d9', marginBottom: 6, fontSize: 13 }}>可落地优化建议</div>
      <div style={{ lineHeight: 2.1, fontSize: 13, display: 'flex', flexDirection: 'column', gap: 2 }}>
        {suggestions}
      </div>
    </div>
  );

  return (
    <div>
      {mod1}
      <div style={{ borderTop: '1px solid #d6e4ff', margin: '10px 0' }} />
      {mod2}
      {mod3 && <><div style={{ borderTop: '1px solid #d6e4ff', margin: '10px 0' }} />{mod3}</>}
      <div style={{ borderTop: '1px solid #d6e4ff', margin: '10px 0' }} />
      {mod4}
    </div>
  );
}

const DashboardPage: React.FC = () => {
  const [dateRange, setDateRange] = useState<{ date_from?: string; date_to?: string }>({});

  const { data: summary, isLoading: summaryLoading } = useSummary(dateRange);
  const { data: categories, isLoading: catLoading } = useCategories();
  const { data: dailyCounts } = useDailyCounts(dateRange);
  const { data: langData } = useLanguage();

  const handleDateChange = (dates: [Dayjs | null, Dayjs | null] | null) => {
    if (dates && dates[0] && dates[1]) {
      setDateRange({ date_from: dates[0].format('YYYY-MM-DD'), date_to: dates[1].format('YYYY-MM-DD') });
    } else {
      setDateRange({});
    }
  };

  const topCategory = summary?.top_categories?.[0]?.name || '-';

  const insightNode = useMemo(() => {
    if (!summary || !categories) return null;
    const total = summary.total_prompts || 0;
    const users = summary.unique_users || 0;
    if (total === 0 || users === 0) return null;

    const cats: { name: string; count: number }[] = categories.llm_category || [];
    const styles: { name: string; count: number }[] = categories.llm_style || [];
    const langs: { language: string; count: number }[] = langData?.language?.distribution || [];

    return buildInsight({
      total,
      users,
      perUser: total / users,
      avgLen: Math.round(summary.avg_prompt_length || 0),
      cats,
      totalCat: cats.reduce((s, c) => s + c.count, 0),
      styles,
      totalStyle: styles.reduce((s, c) => s + c.count, 0),
      langs,
      totalLang: langs.reduce((s, l) => s + l.count, 0),
      langCount: langs.length,
    });
  }, [summary, categories, langData]);

  // Category bar chart
  const categoryOption = {
    tooltip: { trigger: 'axis' as const },
    grid: { left: 160, right: 40, top: 20, bottom: 30 },
    xAxis: { type: 'value' as const },
    yAxis: {
      type: 'category' as const,
      data: [...(categories?.llm_category || [])].reverse().slice(0, 10).map(c => c.name),
      axisLabel: { width: 140, overflow: 'break' as const, fontSize: 12 },
    },
    series: [{
      type: 'bar',
      data: [...(categories?.llm_category || [])].reverse().slice(0, 10).map(c => c.count),
      itemStyle: { color: '#1677ff', borderRadius: [0, 4, 4, 0] },
    }],
  };

  const styleOption = {
    tooltip: { trigger: 'item' as const },
    legend: { orient: 'vertical' as const, right: 10, top: 'center' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      label: { show: false },
      data: (categories?.llm_style || []).slice(0, 8).map(s => ({ name: s.name, value: s.count })),
    }],
  };

  const dailyData = (dailyCounts || []).map(d => ({ date: formatDate(d.date), count: d.count }));
  const dailyOption = {
    tooltip: {
      trigger: 'axis' as const,
      formatter: (params: { name: string; value: number }[]) => {
        const p = params[0];
        return `${p.name}<br/>Prompt 数量：<b>${p.value.toLocaleString()}</b>`;
      },
    },
    grid: { left: 70, right: 40, top: 20, bottom: 40 },
    xAxis: { type: 'category' as const, data: dailyData.map(d => d.date), axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value' as const },
    series: [{
      type: 'line',
      data: dailyData.map(d => d.count),
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      itemStyle: { color: '#1677ff' },
      lineStyle: { color: '#1677ff', width: 2 },
      areaStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(22,119,255,0.3)' },
            { offset: 1, color: 'rgba(22,119,255,0.02)' },
          ],
        },
      },
      label: {
        show: true, position: 'top' as const,
        formatter: (p: { value: number }) => p.value.toLocaleString(),
        fontSize: 11,
      },
    }],
  };

  const langOption = {
    tooltip: { trigger: 'item' as const },
    legend: { orient: 'vertical' as const, right: 10, top: 'center' },
    series: [{
      type: 'pie',
      radius: ['45%', '70%'],
      label: { show: false },
      data: (langData?.language?.distribution || []).slice(0, 8).map(l => ({ name: l.language, value: l.count })),
    }],
  };

  return (
    <div>
      {/* Date Filter */}
      <Card bordered={false} style={{ marginBottom: 16 }}>
        <span style={{ marginRight: 12 }}>时间范围：</span>
        <RangePicker onChange={handleDateChange} allowClear placeholder={['开始日期', '结束日期']} />
        {dateRange.date_from && (
          <span style={{ marginLeft: 12, color: '#666', fontSize: 13 }}>
            {dateRange.date_from} ~ {dateRange.date_to}
          </span>
        )}
      </Card>

      {/* KPI Cards */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={6}>
          <KpiCard title="总 Prompt 数" value={summary?.total_prompts || 0} prefix={<FileTextOutlined />} loading={summaryLoading} />
        </Col>
        <Col xs={12} sm={6}>
          <KpiCard title="独立用户数" value={summary?.unique_users || 0} prefix={<TeamOutlined />} loading={summaryLoading} />
        </Col>
        <Col xs={12} sm={6}>
          <KpiCard title="平均 Prompt 长度" value={summary?.avg_prompt_length || 0} suffix="字符" prefix={<FieldStringOutlined />} loading={summaryLoading} />
        </Col>
        <Col xs={12} sm={6}>
          <KpiCard title="热门类别" value={topCategory} prefix={<TagOutlined />} loading={summaryLoading} />
        </Col>
      </Row>

      {/* Business Insight Card */}
      {insightNode && (
        <div style={{
          background: 'linear-gradient(135deg, #e6f4ff 0%, #f0f7ff 100%)',
          border: '1px solid #91caff',
          borderRadius: 10,
          padding: '16px 20px',
          marginBottom: 24,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 12, gap: 8 }}>
            <span style={{ fontSize: 16 }}>📊</span>
            <span style={{ fontWeight: 700, fontSize: 15, color: '#003eb3' }}>平台总览洞察</span>
          </div>
          {insightNode}
          <div style={{ marginTop: 12, borderTop: '1px solid #bae0ff', paddingTop: 8 }}>
            <Text style={{ fontSize: 12, color: '#8c8c8c' }}>
              💡 以上洞察基于实时数据生成，可点击「运行分析」更新
            </Text>
          </div>
        </div>
      )}

      {/* Charts */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} lg={14}>
          <Card title="类别分布（前 10）" bordered={false}>
            <EChartsWrapper option={categoryOption} loading={catLoading} empty={!categories?.llm_category?.length} height={360} />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="风格分布" bordered={false}>
            <EChartsWrapper option={styleOption} loading={catLoading} empty={!categories?.llm_style?.length} height={360} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={14}>
          <Card title="每日 Prompt 量" bordered={false}>
            <EChartsWrapper option={dailyOption} empty={!dailyCounts?.length} height={300} />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="语言分布" bordered={false}>
            <EChartsWrapper option={langOption} empty={!langData?.language?.distribution?.length} height={300} />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default DashboardPage;
