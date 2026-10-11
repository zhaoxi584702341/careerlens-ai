# ==================== java-service/Dockerfile ====================
# 多阶段构建：编译阶段用 Maven 官方镜像，运行阶段用精简 JRE 镜像

# ---------- 阶段一：编译打包 ----------
FROM maven:3.9-eclipse-temurin-17 AS builder

WORKDIR /build

# 先复制 pom.xml 并预下载依赖，利用层缓存加速后续构建
COPY pom.xml .
RUN mvn -B dependency:go-offline

# 复制源码并执行打包，跳过测试以加快镜像构建
COPY src ./src
RUN mvn -B clean package -DskipTests

# ---------- 阶段二：运行 ----------
FROM eclipse-temurin:17-jre-jammy

# 时区与 JVM 运行参数
ENV TZ=Asia/Shanghai \
    JAVA_OPTS="-Xms256m -Xmx512m -Djava.security.egd=file:/dev/./urandom"

WORKDIR /app

# 创建非 root 用户
RUN useradd --create-home --shell /usr/sbin/nologin appuser
USER appuser

# 从编译阶段复制可执行 jar
COPY --from=builder /build/target/java-service-0.0.1-SNAPSHOT.jar app.jar

EXPOSE 8080

# 启动 Spring Boot 应用
ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar"]
