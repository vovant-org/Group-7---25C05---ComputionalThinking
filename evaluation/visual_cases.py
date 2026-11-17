"""Hand-written cases for the Topic-aware Visual Engine benchmark.

DATA CAVEAT: topics, sentences and the GOLD labels (domain of each topic; for each sentence the objects of the
engine's vocabulary that would be a sensible picture) were written by the AI assistant, NOT yet reviewed by the
team, and the sentences are short generic statements, not verified research. Use the numbers as a regression
and iteration record, not as a measurement of quality on real videos.
"""
CASES = [
    ("sleep_en", "Why do we need sleep?", "sleep", [
        ("At night the body rests and the brain sorts the memories of the day.", {"moon", "brain", "bed"}),
        ("A regular bedtime keeps the body clock in a steady rhythm.", {"clock", "bed", "moon"}),
        ("While you sleep, the heart slows down and the body repairs itself.", {"heart", "bed"}),
        ("Dreams may help the brain connect new facts with old ones.", {"bed", "brain"}),
        ("Too little sleep makes it hard to learn and to remember lessons.", {"bed", "brain", "book"}),
        ("A dark room and a calm mind help you fall asleep faster.", {"bed", "moon"})]),
    ("sleep_vi", "Tại sao chúng ta cần ngủ?", "sleep", [
        ("Giấc ngủ giúp não sắp xếp lại trí nhớ của một ngày dài.", {"bed", "brain"}),
        ("Vào ban đêm, đồng hồ sinh học báo cho cơ thể biết đã đến giờ nghỉ.", {"moon", "clock"}),
        ("Khi ngủ, tim đập chậm hơn và cơ thể được phục hồi.", {"bed", "heart"}),
        ("Ngôi sao và mặt trăng nhắc ta đi ngủ đúng giờ mỗi tối.", {"star", "moon", "clock"}),
        ("Thức khuya nhiều ngày làm ta khó tập trung và dễ quên.", {"moon", "brain", "bed"}),
        ("Một giấc mơ đẹp bắt đầu từ một căn phòng yên tĩnh.", {"bed"})]),
    ("inflation_en", "Why do prices keep rising?", "economy", [
        ("Money moves around: people spend it at shops and shops deposit it in the bank.", {"coin", "bank", "basket"}),
        ("When prices rise, each coin buys a smaller basket of goods.", {"tag", "coin", "basket"}),
        ("Central banks raise interest rates to cool prices.", {"bank", "bars_up", "tag"}),
        ("Inflation measures how fast the price of the same goods goes up.", {"tag", "bars_up"}),
        ("Savings in the bank lose value when inflation is higher than interest.", {"coin", "bank"}),
        ("Shops buy goods and sell them again with a higher price tag.", {"basket", "tag"})]),
    ("inflation_vi", "Tại sao giá cả cứ tăng?", "economy", [
        ("Tiền chảy từ người mua sang cửa hàng rồi gửi vào ngân hàng.", {"coin", "bank", "basket"}),
        ("Khi giá tăng, một đồng tiền chỉ mua được ít hàng hóa hơn.", {"tag", "coin", "basket"}),
        ("Ngân hàng trung ương tăng lãi suất để hạ nhiệt giá cả.", {"bank", "bars_up", "tag"}),
        ("Lạm phát cho biết giá của cùng một giỏ hàng tăng nhanh đến đâu.", {"bars_up", "basket", "tag"}),
        ("Tiền tiết kiệm mất giá khi lạm phát cao hơn lãi suất.", {"coin", "bank", "bars_up"}),
        ("Chi phí sản xuất tăng khiến giá bán cũng tăng theo.", {"tag", "bars_up"})]),
    ("flood_en", "Why does Ho Chi Minh City flood in heavy rain?", "weather", [
        ("Heavy rain falls on a city where most of the ground is covered by concrete.", {"drop", "cloud", "building"}),
        ("High tides push river water up, so the drains cannot empty into the river.", {"flood", "fish", "drop"}),
        ("When the water level rises, streets and buildings start to flood.", {"flood", "building", "drop"}),
        ("Clouds from the monsoon bring rain for many hours in the afternoon.", {"cloud", "drop"}),
        ("Old drainage pipes cannot carry this much water away quickly.", {"flood", "drop"}),
        ("Citizens check the weather and avoid low streets during a storm.", {"cloud", "building"})]),
    ("flood_vi", "Tại sao thành phố Hồ Chí Minh bị ngập khi mưa lớn?", "weather", [
        ("Mưa lớn đổ xuống thành phố nơi phần lớn mặt đất được phủ bê tông.", {"drop", "cloud", "building"}),
        ("Triều cường dâng cao nên hệ thống thoát nước không xả ra sông được.", {"flood", "drop", "fish"}),
        ("Khi mực nước dâng lên, đường phố và nhà cửa bắt đầu ngập.", {"flood", "building"}),
        ("Mây từ gió mùa mang mưa kéo dài nhiều giờ vào buổi chiều.", {"cloud", "drop"}),
        ("Cống thoát nước cũ không chuyển nước đi kịp.", {"flood", "drop"}),
        ("Người dân theo dõi thời tiết để tránh những con đường thấp.", {"cloud", "building"})]),
    ("space_en", "How do planets move around the sun?", "space", [
        ("The sun holds every planet in its orbit with gravity.", {"planet", "sun"}),
        ("A rocket must reach very high speed to leave the Earth.", {"rocket", "earth"}),
        ("Planets close to the sun travel faster than far planets.", {"planet"}),
        ("At night the moon and the stars seem to move across the sky.", {"moon", "star"}),
        ("The Earth turns once a day, so we see day and night.", {"earth", "sun", "moon"}),
        ("A satellite circles the Earth and sends pictures back.", {"rocket", "earth"})]),
    ("nature_en", "How do plants and animals live together?", "nature", [
        ("A seed needs water and sunlight to sprout and grow into a tree.", {"sprout", "drop", "sun", "tree"}),
        ("A deer walks through the forest and eats leaves.", {"animal", "tree"}),
        ("Birds fly over the trees and carry seeds to new places.", {"bird", "tree", "sprout"}),
        ("Fish swim in the river that the rain fills.", {"fish", "drop"}),
        ("The sun gives energy to every plant in the garden.", {"sun", "sprout", "tree"}),
        ("A herd of elephants migrates when the rivers dry up.", {"animal", "drop", "fish"})]),
    ("tech_en", "How does the internet work?", "tech", [
        ("A computer sends data over the network in small packets.", {"chip", "signal"}),
        ("Each packet travels through many routers before it arrives.", {"signal"}),
        ("A chip in your phone turns the signal back into a page.", {"chip", "signal"}),
        ("Software decides how to read and show the data.", {"chip", "signal"}),
        ("Satellites help the internet reach remote places.", {"rocket", "signal"}),
        ("Students use the network to read books and learn.", {"book", "signal"})]),
]
