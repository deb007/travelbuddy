# Travel Expense Tracker - Product Requirements Document

## 1. Product Overview

### 1.1 Purpose
A personal travel expense tracking app for a 6D5N vacation to Singapore and Malaysia, handling multi-currency expenses with budget management and real-time spending insights.

### 1.2 Scope
MVP for personal use focusing on core expense tracking, budget management, and spending analytics across INR, SGD, and MYR currencies.

### 1.3 User
Single family (user, wife, son) traveling from Delhi to Singapore and Malaysia.

## 2. Core Features

### 2.1 Multi-Currency Budget Management
- **Overall Budget Setup**: Set maximum spending limits for INR, SGD, and MYR
- **Progress Tracking**: Visual progress bars showing spent vs remaining budget for each currency
- **Real-time Balance**: Live updates as expenses are logged
- **Budget Alerts**: Visual warnings when approaching 80% and 90% of budget limits

### 2.2 Expense Logging
- **Quick Entry Form**: Simple form with amount, currency, category, and optional description
- **Currency Selection**: Dropdown with INR, SGD, MYR options
- **Category Tags**: Predefined categories (Food, Transport, Shopping, Accommodation, Activities, Visa/Fees, Insurance, Forex, SIM, Other)
- **Date Selection**: Manual date picker for pre-trip expenses (bookings, visa, etc.)
- **Payment Method**: Track cash vs forex card vs regular card expenses

### 2.3 Timeline Management
- **Pre-Trip Phase**: Track booking expenses 3-4 months before travel
- **Trip Phase**: Daily expense tracking during the 6-day vacation
- **Phase Toggle**: Easy switch between pre-trip and trip view

### 2.4 Forex Card Tracking
- **Card Balance Setup**: Set initial loaded amounts for SGD and MYR forex cards
- **Balance Deduction**: Automatic deduction from forex card balance when selected as payment method
- **Low Balance Alerts**: Notification when forex card balance drops below 20%

### 2.5 Exchange Rate Integration
- **Live Rates**: Fetch current exchange rates for INR-SGD and INR-MYR
- **Rate Display**: Show current rates in the currency selection area
- **INR Equivalent**: Display INR equivalent for all foreign currency expenses

### 2.6 Spending Analytics
- **Daily Average**: Calculate average daily spend across all currencies (INR equivalent)
- **Days Remaining**: Track remaining days of trip
- **Daily Available Budget**: Calculate daily spending allowance based on remaining budget and days
- **Currency Breakdown**: Visual breakdown of spending by currency
- **Category Analysis**: Spending distribution across categories
- **Trend Tracking**: Daily spending patterns during the trip

## 3. User Interface Requirements

### 3.1 Dashboard
- **Budget Overview**: Three progress bars (INR, SGD, MYR) with spent/remaining amounts
- **Daily Insights**: Today's spending, daily average, and recommended daily limit
- **Quick Stats**: Total expenses, days remaining, exchange rates
- **Phase Indicator**: Clear indication of pre-trip vs trip phase

### 3.2 Expense Entry Screen
- **Amount Input**: Large numeric keypad-friendly input
- **Currency Selector**: Prominent currency buttons (INR/SGD/MYR)
- **Category Tags**: Horizontal scrollable tag selection
- **Payment Method**: Radio buttons for Cash, Forex Card, Regular Card
- **Date Picker**: Default to current date, manual override available
- **Save Button**: Large, prominent save action

### 3.3 Expense List
- **Chronological List**: Recent expenses first with date grouping
- **Currency Icons**: Clear currency indicators
- **Category Colors**: Color-coded category tags
- **Edit/Delete**: Swipe actions for expense management

### 3.4 Analytics Screen
- **Budget Charts**: Donut charts for each currency showing spent vs remaining
- **Daily Trend**: Line graph of daily spending
- **Category Breakdown**: Horizontal bar chart of category-wise spending
- **Key Metrics**: Cards showing daily average, remaining daily budget, etc.

## 4. Technical Requirements

### 4.1 Data Storage
- **Local Storage**: All data stored locally (no cloud sync required for MVP)
- **Data Structure**: JSON-based expense records with currency, amount, category, date, payment method

### 4.2 Exchange Rate API
- **Provider**: Free exchange rate API (e.g., ExchangeRate-API or Fixer.io free tier)
- **Caching**: Cache rates for 1 hour to minimize API calls
- **Fallback**: Manual rate input if API unavailable

### 4.3 Platform
- **Web App**: Responsive web application accessible on mobile devices
- **Offline Support**: Basic offline functionality for expense logging
- **Browser Compatibility**: Modern mobile browsers (Chrome, Safari)

## 5. Data Models

### 5.1 Expense Record
```javascript
{
  id: string,
  amount: number,
  currency: 'INR' | 'SGD' | 'MYR',
  category: string,
  description: string (optional),
  date: ISO date string,
  paymentMethod: 'cash' | 'forex' | 'card',
  inrEquivalent: number,
  exchangeRate: number
}
```

### 5.2 Budget Configuration
```javascript
{
  currencies: {
    INR: { max: number, spent: number },
    SGD: { max: number, spent: number },
    MYR: { max: number, spent: number }
  },
  forexCards: {
    SGD: { loaded: number, spent: number },
    MYR: { loaded: number, spent: number }
  },
  tripDates: {
    start: ISO date,
    end: ISO date
  }
}
```

## 6. Success Metrics

### 6.1 Functional Success
- **Budget Adherence**: Stay within set currency limits
- **Expense Tracking**: Log all significant expenses (>₹100 equivalent)
- **Accuracy**: Maintain <5% discrepancy between logged and actual expenses

### 6.2 Usability Success
- **Entry Time**: Log expense in <30 seconds
- **Daily Usage**: Check app at least once daily during trip
- **Insights Value**: Daily budget recommendations help guide spending decisions

## 7. Future Enhancements (Post-MVP)
- Photo receipt capture and OCR
- Multiple trip support
- Expense sharing between family members
- Export functionality (PDF reports)
- Cloud sync and backup
- Advanced analytics and insights
- Integration with banking APIs
- Recurring expense templates

## 8. Development Timeline
- **Phase 1**: Core expense logging and budget setup (Week 1)
- **Phase 2**: Analytics and exchange rate integration (Week 2)  
- **Phase 3**: UI polish and testing (Week 3)
- **Pre-Trip Launch**: 2-3 weeks before travel departure