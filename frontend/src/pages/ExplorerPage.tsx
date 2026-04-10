import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Table, Input, Select, Row, Col, Button, Tag, Space, Tooltip, Typography } from 'antd';
import { SearchOutlined, DownloadOutlined, ReloadOutlined, EyeOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { fetchPrompts, exportCsv } from '../api/endpoints';
import { useCategories } from '../hooks/useAnalysisData';
import type { PromptRecord } from '../types';

const { Text } = Typography;

const ExplorerPage: React.FC = () => {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState<string | undefined>();
  const [style, setStyle] = useState<string | undefined>();
  const [searchInput, setSearchInput] = useState('');

  const { data: categories } = useCategories();

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['prompts', page, pageSize, search, category, style],
    queryFn: () => fetchPrompts({ page, page_size: pageSize, search: search || undefined, category, style }),
    staleTime: 60 * 1000,
  });

  const handleSearch = () => {
    setSearch(searchInput);
    setPage(1);
  };

  const handleExport = async () => {
    await exportCsv();
  };

  const columns = [
    {
      title: 'Prompt 内容',
      dataIndex: 'prompt',
      key: 'prompt',
      width: 350,
      render: (text: string) => (
        <Tooltip title={text}>
          <Text ellipsis style={{ maxWidth: 330, display: 'inline-block' }}>{text}</Text>
        </Tooltip>
      ),
    },
    {
      title: '类别',
      dataIndex: 'llm_category',
      key: 'llm_category',
      width: 150,
      render: (v: string) => v ? <Tag color="blue">{v}</Tag> : '-',
    },
    {
      title: '风格',
      dataIndex: 'llm_style',
      key: 'llm_style',
      width: 110,
      render: (v: string) => v ? <Tag color="green">{v}</Tag> : '-',
    },
    {
      title: '用途',
      dataIndex: 'llm_use_case',
      key: 'llm_use_case',
      width: 120,
      render: (v: string) => v ? <Tag color="orange">{v}</Tag> : '-',
    },
    {
      title: '对象',
      dataIndex: 'llm_object',
      key: 'llm_object',
      width: 150,
      ellipsis: true,
    },
    {
      title: '颜色',
      dataIndex: 'llm_color',
      key: 'llm_color',
      width: 150,
      render: (v: string) => v || '-',
    },
    {
      title: '关键词',
      dataIndex: 'llm_keyword',
      key: 'llm_keyword',
      width: 180,
      ellipsis: true,
    },
    {
      title: '日期',
      dataIndex: 'pt',
      key: 'pt',
      width: 100,
      sorter: true,
    },
    {
      title: '用户 ID',
      dataIndex: 'user_id',
      key: 'user_id',
      width: 100,
      ellipsis: true,
    },
    {
      title: '操作',
      key: 'action',
      width: 70,
      fixed: 'right' as const,
      render: (_: unknown, record: PromptRecord) => (
        <Button
          type="link"
          size="small"
          icon={<EyeOutlined />}
          onClick={(e) => { e.stopPropagation(); navigate(`/prompt/${record.project_id}`); }}
        />
      ),
    },
  ];

  return (
    <div>
      <Card bordered={false} style={{ marginBottom: 16 }}>
        <Row gutter={[12, 12]} align="middle">
          <Col flex="auto">
            <Input
              placeholder="搜索 Prompt..."
              prefix={<SearchOutlined />}
              value={searchInput}
              onChange={e => setSearchInput(e.target.value)}
              onPressEnter={handleSearch}
              allowClear
            />
          </Col>
          <Col>
            <Select
              allowClear
              placeholder="类别"
              style={{ width: 180 }}
              value={category}
              onChange={v => { setCategory(v); setPage(1); }}
              options={(categories?.llm_category || []).map(c => ({
                label: c.name,
                value: c.name,
              }))}
            />
          </Col>
          <Col>
            <Select
              allowClear
              placeholder="风格"
              style={{ width: 140 }}
              value={style}
              onChange={v => { setStyle(v); setPage(1); }}
              options={(categories?.llm_style || []).map(s => ({
                label: s.name,
                value: s.name,
              }))}
            />
          </Col>
          <Col>
            <Space>
              <Button type="primary" icon={<SearchOutlined />} onClick={handleSearch}>
                搜索
              </Button>
              <Button icon={<ReloadOutlined />} onClick={() => refetch()}>
                刷新
              </Button>
              <Button icon={<DownloadOutlined />} onClick={handleExport}>
                导出 CSV
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>

      <Card bordered={false}>
        <Table<PromptRecord>
          columns={columns}
          dataSource={data?.data}
          loading={isLoading}
          rowKey="project_id"
          scroll={{ x: 1500 }}
          onRow={(record) => ({
            onClick: () => navigate(`/prompt/${record.project_id}`),
            style: { cursor: 'pointer' },
          })}
          pagination={{
            current: page,
            pageSize,
            total: data?.total || 0,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 条 Prompt`,
            onChange: (p, ps) => { setPage(p); setPageSize(ps); },
          }}
          size="small"
        />
      </Card>
    </div>
  );
};

export default ExplorerPage;
