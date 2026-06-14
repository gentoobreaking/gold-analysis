/**
 * News 頁面 - 黃金市場新聞資訊
 * 目前使用靜態 mock 資料，未串接真實新聞 API
 */
import React, { useState } from 'react';

// Mock 新聞資料
const MOCK_NEWS = [
  {
    id: 1,
    title: '聯準會利率決策出爐，黃金短線走高突破 2,400 美元',
    source: 'Bloomberg',
    time: '2026-04-17 14:30',
    summary:
      '聯準會宣布維持利率不變，並暗示下半年可能降息一次。美元指數應聲回落，國際金價短線飆升，一度觸及 2,418 美元。分析師指出，低利率環境對黃金形成實質支撐，建議持續關注美債殖利率走勢。',
    tags: ['聯準會', '利率', '美元'],
  },
  {
    id: 2,
    title: '地緣政治緊張加劇，避險需求推升金價',
    source: 'Reuters',
    time: '2026-04-16 09:15',
    summary:
      '中東局勢升級，帶動投資人避險情緒升溫。黃金ETF 單日淨流入超過 20 噸，創近三個月新高。機構投資者加碼黃金倉位，反映全球宏觀不確定性仍高。',
    tags: ['地緣政治', '避險', 'ETF'],
  },
  {
    id: 3,
    title: '台灣銀行黃金存摺牌價創歷史新高，突破 5,000 元',
    source: '鉅亨網',
    time: '2026-04-15 11:00',
    summary:
      '受國際金價上漲帶動，台灣銀行黃金存摺賣出價正式突破新台幣 5,000 元大關，創下歷史紀錄。民眾申購意願踴躍，黃金條塊及相關理財商品詢問度明顯增加。',
    tags: ['台灣銀行', '黃金存摺', '歷史新高'],
  },
  {
    id: 4,
    title: '中國人民銀行連續六個月增持黃金儲備',
    source: 'Financial Times',
    time: '2026-04-14 16:45',
    summary:
      '根據人行最新數據，3 月黃金儲備再增加 12 噸，為連續第六個月增持。各國央行去美元化趨勢持續，新興市場國家紛紛提高黃金在外匯存底中的比重。',
    tags: ['央行', '黃金儲備', '去美元化'],
  },
  {
    id: 5,
    title: '技術面：黃金 RSI 接近超買區，短線可能震盪整理',
    source: 'Investing.com',
    time: '2026-04-13 20:00',
    summary:
      '從日線圖觀察，黃金14日RSI 升至 72，已進入超買區域。短線或有獲利了結壓力，需留意 2,350 美元支撐是否有效。多空雙方在 2,400 美元關卡拉鋸，等待新驅動因素突破。',
    tags: ['技術分析', 'RSI', '支撐阻力'],
  },
  {
    id: 6,
    title: '印度婚禮季結束，實體需求放緩拖累金價',
    source: 'CNBC',
    time: '2026-04-12 08:30',
    summary:
      '印度傳統婚禮旺季進入尾聲，珠寶商採購熱潮消退，實體需求出現回落。作為全球第二大黃金消費國，印度需求降溫短期內對價格形成一定壓力，但仍獲逢低買盤支撐。',
    tags: ['印度', '實體需求', '珠寶'],
  },
  {
    id: 7,
    title: '黃金礦商財報亮眼，大型金礦公司營收年增 15%',
    source: 'MarketWatch',
    time: '2026-04-11 14:00',
    summary:
      '全球主要黃金礦商相繼公布季度財報，受金價上漲帶動，整體營收表現亮眼。Newmont、Barrick Gold 等龍頭廠商皆上修全年產量指引，礦商類股有望持續吸引市場目光。',
    tags: ['礦商', '財報', '股價'],
  },
  {
    id: 8,
    title: '比特幣與黃金走勢分化，數位黃金熱度降溫',
    source: 'CoinDesk',
    time: '2026-04-10 17:20',
    summary:
      '加密貨幣市場近週回調，比特幣與黃金的相關性降至 0.3 以下。市場人士認為，兩者在宏觀避險屬性上逐漸走出各自方向，黃金作為傳統避險資產的地位仍穩固。',
    tags: ['比特幣', '加密貨幣', '相關性'],
  },
];

interface NewsCardProps {
  news: (typeof MOCK_NEWS)[number];
  defaultExpanded?: boolean;
}

const NewsCard: React.FC<NewsCardProps> = ({ news, defaultExpanded = false }) => {
  const [expanded, setExpanded] = useState(defaultExpanded);

  return (
    <div className="bg-slate-700/50 rounded-lg p-4 border border-slate-600 hover:border-yellow-500/40 transition-colors">
      {/* Header */}
      <button
        className="w-full text-left flex items-start justify-between gap-3"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex-1">
          <h3 className="text-white font-semibold text-sm leading-snug">{news.title}</h3>
          <div className="flex items-center gap-3 mt-2 text-xs text-gray-400">
            <span className="bg-slate-600 px-2 py-0.5 rounded">{news.source}</span>
            <span>🕐 {news.time}</span>
          </div>
        </div>
        <span className="text-gray-400 text-lg flex-shrink-0 mt-0.5">
          {expanded ? '▲' : '▼'}
        </span>
      </button>

      {/* Expandable content */}
      {expanded && (
        <div className="mt-3 pt-3 border-t border-slate-600 animate-in slide-in-from-top-1 duration-200">
          <p className="text-gray-300 text-sm leading-relaxed">{news.summary}</p>
          <div className="flex flex-wrap gap-2 mt-3">
            {news.tags.map((tag) => (
              <span
                key={tag}
                className="text-xs bg-yellow-500/10 text-yellow-400 border border-yellow-500/20 px-2 py-0.5 rounded"
              >
                #{tag}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

const News: React.FC = () => {
  const [expandedId, setExpandedId] = useState<number | null>(1); // 第一條預設展開

  return (
    <div className="space-y-6 p-4">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-white">📰 新聞</h2>
        <p className="text-gray-400 text-sm">黃金市場新聞動態</p>
      </div>

      {/* Info banner */}
      <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-3 flex items-start gap-3">
        <span className="text-yellow-400 text-lg flex-shrink-0">ℹ️</span>
        <p className="text-sm text-gray-300">
          目前顯示為靜態模擬資料，待串接真實新聞 API（如 NewsAPI、Google News RSS）後將自動更新。
        </p>
      </div>

      {/* News list */}
      <div className="space-y-3">
        {MOCK_NEWS.map((news) => (
          <NewsCard
            key={news.id}
            news={news}
            defaultExpanded={news.id === expandedId}
          />
        ))}
      </div>
    </div>
  );
};

export default News;
