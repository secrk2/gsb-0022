FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /build
# 先单独拷贝 pom，利用构建层缓存依赖
COPY pom.xml .
RUN mvn -B -q dependency:go-offline
COPY src ./src
RUN mvn -B -q clean package -DskipTests

FROM eclipse-temurin:17-jre
# JVM 会读取 TZ 环境变量作为默认时区；tzdata 兜底供系统工具
ENV TZ=Europe/London \
    JAVA_OPTS="-XX:MaxRAMPercentage=75.0"
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata curl \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /var/log/app
WORKDIR /app
COPY --from=build /build/target/app.jar /app/app.jar
EXPOSE 8080
ENTRYPOINT ["sh", "-c", "exec java $JAVA_OPTS -jar /app/app.jar"]
